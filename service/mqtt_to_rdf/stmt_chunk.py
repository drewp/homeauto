import itertools
import logging
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Set, cast

from rdflib.graph import Graph
from rdflib.term import BNode, Literal, Node, URIRef, Variable

from candidate_binding import CandidateBinding
from inference_types import BindingUnknown, Inconsistent, Triple
from rdf_debug import graphDump

log = logging.getLogger('infer')

INDENT = '    '


@dataclass
class Chunk:  # rename this
    """a statement, maybe with variables in it, except *the object can be an rdf list*.
    This is done to optimize list comparisons (a lot) at the very minor expense of not
    handling certain exotic cases, such as a branching list.

    Also the subject could be a list, e.g. for (?x ?y) math:sum ?z .

    Also a function call in a rule is always contained in exactly one chunk.
    """
    # all immutable
    primary: Triple
    subjList: Optional[List[Node]]
    objList: Optional[List[Node]]

    def __post_init__(self):
        self.predicate = self.primary[1]
        self.sortKey = (self.primary, tuple(self.subjList or []), tuple(self.objList or []))

    def __hash__(self):
        return hash(self.sortKey)

    def __gt__(self, other):
        return self.sortKey > other.sortKey

    @classmethod
    def splitGraphIntoChunks(cls, graph: Graph) -> Iterator['Chunk']:
        for stmt in graph:
            yield cls(primary=stmt, subjList=None, objList=None)

    def totalBindingIfThisStmtWereTrue(self, prevBindings: CandidateBinding, proposed: 'Chunk') -> CandidateBinding:
        outBinding = prevBindings.copy()
        for rt, ct in zip(self.primary, proposed.primary):
            if isinstance(rt, (Variable, BNode)):
                if outBinding.contains(rt) and outBinding.applyTerm(rt) != ct:
                    msg = f'{rt=} {ct=} {outBinding=}' if log.isEnabledFor(logging.DEBUG) else ''
                    raise Inconsistent(msg)
                outBinding.addNewBindings(CandidateBinding({rt: ct}))
        return outBinding

    def myMatches(self, g: 'ChunkedGraph') -> List['Chunk']:
        """Chunks from g where self, which may have BindableTerm wildcards, could match that chunk in g."""
        out: List['Chunk'] = []
        log.debug(f'{self}.myMatches({g}')
        for ch in g.allChunks():
            if self.matches(ch):
                out.append(ch)
        #out.sort()  # probably leftover- remove?
        return out

    # could combine this and totalBindingIf into a single ChunkMatch object
    def matches(self, other: 'Chunk') -> bool:
        """does this Chunk with potential BindableTerm wildcards match other?"""
        for selfTerm, otherTerm in zip(self.primary, other.primary):
            if not isinstance(selfTerm, (Variable, BNode)) and selfTerm != otherTerm:
                return False
        return True

    def __repr__(self):
        return graphDump([self.primary]) + (''.join('+%s' % obj for obj in self.objList) if self.objList else '')

    def isFunctionCall(self, functionsFor) -> bool:
        return bool(list(functionsFor(cast(URIRef, self.predicate))))

    def isStatic(self) -> bool:
        return (stmtIsStatic(self.primary) and all(termIsStatic(s) for s in (self.subjList or [])) and
                all(termIsStatic(s) for s in (self.objList or [])))


def stmtIsStatic(stmt: Triple) -> bool:
    return all(termIsStatic(t) for t in stmt)


def termIsStatic(term: Node) -> bool:
    return isinstance(term, (URIRef, Literal))


def applyChunky(cb: CandidateBinding, g: Iterable[Chunk], returnBoundStatementsOnly=True) -> Iterator[Chunk]:
    for stmt in g:
        try:
            bound = Chunk(
                (
                    cb.applyTerm(stmt.primary[0], returnBoundStatementsOnly),  #
                    cb.applyTerm(stmt.primary[1], returnBoundStatementsOnly),  #
                    cb.applyTerm(stmt.primary[2], returnBoundStatementsOnly)),
                subjList=None,
                objList=None)
        except BindingUnknown:
            log.debug(f'{INDENT*7} CB.apply cant bind {stmt} using {cb.binding}')

            continue
        log.debug(f'{INDENT*7} CB.apply took {stmt} to {bound}')

        yield bound


class ChunkedGraph:
    """a Graph converts 1-to-1 with a ChunkedGraph, where the Chunks have
    combined some statements together. (The only excpetion is that bnodes for
    rdf lists are lost)"""

    def __init__(
            self,
            graph: Graph,
            functionsFor  # get rid of this- i'm just working around a circular import
    ):
        self.chunksUsedByFuncs: Set[Chunk] = set()
        self.staticChunks: Set[Chunk] = set()
        self.patternChunks: Set[Chunk] = set()
        for c in Chunk.splitGraphIntoChunks(graph):
            if c.isFunctionCall(functionsFor):
                self.chunksUsedByFuncs.add(c)
            elif c.isStatic():
                self.staticChunks.add(c)
            else:
                self.patternChunks.add(c)

    def allPredicatesExceptFunctions(self) -> Set[Node]:
        return set(ch.predicate for ch in itertools.chain(self.staticChunks, self.patternChunks))

    def noPredicatesAppear(self, preds: Iterable[Node]) -> bool:
        return self.allPredicatesExceptFunctions().isdisjoint(preds)

    def __nonzero__(self):
        return bool(self.chunksUsedByFuncs) or bool(self.staticChunks) or bool(self.patternChunks)

    def __repr__(self):
        return f'ChunkedGraph({self.__dict__})'

    def allChunks(self) -> Iterable[Chunk]:
        yield from itertools.chain(self.staticChunks, self.patternChunks, self.chunksUsedByFuncs)

    def value(self, subj, pred) -> Node:  # throwaway
        for s in self.allChunks():
            s = s.primary
            if (s[0], s[1]) == (subj, pred):
                return s[2]
        raise ValueError("value not found")

    def __contains__(self, ch: Chunk) -> bool:
        return ch in self.allChunks()
