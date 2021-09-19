import itertools
import logging
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Set, Tuple, cast

from rdflib.graph import Graph
from rdflib.namespace import RDF
from rdflib.term import BNode, Literal, Node, URIRef, Variable

from candidate_binding import CandidateBinding
from inference_types import BindingUnknown, Inconsistent, Triple
from rdf_debug import graphDump

log = logging.getLogger('infer')

INDENT = '    '

ChunkPrimaryTriple = Tuple[Optional[Node], Node, Optional[Node]]


@dataclass
class Chunk:  # rename this
    """a statement, maybe with variables in it, except *the object can be an rdf list*.
    This is done to optimize list comparisons (a lot) at the very minor expense of not
    handling certain exotic cases, such as a branching list.

    Also the subject could be a list, e.g. for (?x ?y) math:sum ?z .

    Also a function call in a rule is always contained in exactly one chunk.
    """
    # all immutable
    primary: ChunkPrimaryTriple
    subjList: Optional[List[Node]] = None
    objList: Optional[List[Node]] = None

    def __post_init__(self):
        if not (((self.primary[0] is not None) ^ (self.subjList is not None)) and
                ((self.primary[2] is not None) ^ (self.objList is not None))):
            raise TypeError("invalid chunk init")
        self.predicate = self.primary[1]
        self.sortKey = (self.primary, tuple(self.subjList or []), tuple(self.objList or []))

    def __hash__(self):
        return hash(self.sortKey)

    def __gt__(self, other):
        return self.sortKey > other.sortKey

    def _allTerms(self) -> Iterator[Node]:
        """the terms in `primary` plus the lists. Output order is undefined but stable between same-sized Chunks"""
        yield self.primary[1]
        if self.primary[0] is not None:
            yield self.primary[0]
        else:
            yield from cast(List[Node], self.subjList)
        if self.primary[2] is not None:
            yield self.primary[2]
        else:
            yield from cast(List[Node], self.objList)

    def totalBindingIfThisStmtWereTrue(self, prevBindings: CandidateBinding, proposed: 'Chunk') -> CandidateBinding:
        outBinding = prevBindings.copy()
        for rt, ct in zip(self._allTerms(), proposed._allTerms()):
            if isinstance(rt, (Variable, BNode)):
                if outBinding.contains(rt) and outBinding.applyTerm(rt) != ct:
                    msg = f'{rt=} {ct=} {outBinding=}' if log.isEnabledFor(logging.DEBUG) else ''
                    raise Inconsistent(msg)
                outBinding.addNewBindings(CandidateBinding({rt: ct}))
        return outBinding

    def myMatches(self, g: 'ChunkedGraph') -> List['Chunk']:
        """Chunks from g where self, which may have BindableTerm wildcards, could match that chunk in g."""
        out: List['Chunk'] = []
        log.debug(f'{INDENT*6} {self}.myMatches({g}')
        for ch in g.allChunks():
            if self.matches(ch):
                out.append(ch)
        return out

    # could combine this and totalBindingIf into a single ChunkMatch object
    def matches(self, other: 'Chunk') -> bool:
        """does this Chunk with potential BindableTerm wildcards match other?"""
        for selfTerm, otherTerm in zip(self._allTerms(), other._allTerms()):
            if not isinstance(selfTerm, (Variable, BNode)) and selfTerm != otherTerm:
                return False
        return True

    def __repr__(self):
        pre = ('+'.join('%s' % elem for elem in self.subjList) + '+' if self.subjList else '')
        post = ('+' + '+'.join('%s' % elem for elem in self.objList) if self.objList else '')
        return pre + repr(self.primary) + post

    def isFunctionCall(self, functionsFor) -> bool:
        return bool(list(functionsFor(cast(URIRef, self.predicate))))

    def isStatic(self) -> bool:
        return all(_termIsStatic(s) for s in self._allTerms())

    def apply(self, cb: CandidateBinding, returnBoundStatementsOnly=True) -> 'Chunk':
        """Chunk like this one but with cb substitutions applied. If the flag is
        True, we raise BindingUnknown instead of leaving a term unbound"""
        fn = lambda t: cb.applyTerm(t, returnBoundStatementsOnly)
        return Chunk(
            (
                fn(self.primary[0]) if self.primary[0] is not None else None,  #
                fn(self.primary[1]),  #
                fn(self.primary[2]) if self.primary[2] is not None else None),
            subjList=[fn(t) for t in self.subjList] if self.subjList else None,
            objList=[fn(t) for t in self.objList] if self.objList else None,
        )


def _termIsStatic(term: Optional[Node]) -> bool:
    return isinstance(term, (URIRef, Literal)) or term is None


def applyChunky(cb: CandidateBinding, g: Iterable[Chunk], returnBoundStatementsOnly=True) -> Iterator[Chunk]:
    for chunk in g:
        try:
            bound = chunk.apply(cb, returnBoundStatementsOnly=returnBoundStatementsOnly)
        except BindingUnknown:
            log.debug(f'{INDENT*7} CB.apply cant bind {chunk} using {cb.binding}')

            continue
        log.debug(f'{INDENT*7} CB.apply took {chunk} to {bound}')

        yield bound


class ChunkedGraph:
    """a Graph converts 1-to-1 with a ChunkedGraph, where the Chunks have
    combined some statements together. (The only exception is that bnodes for
    rdf lists are lost)"""

    def __init__(
            self,
            graph: Graph,
            functionsFor  # get rid of this- i'm just working around a circular import
    ):
        self.chunksUsedByFuncs: Set[Chunk] = set()
        self.staticChunks: Set[Chunk] = set()
        self.patternChunks: Set[Chunk] = set()

        firstNodes = {}
        restNodes = {}
        graphStmts = set()
        for s, p, o in graph:
            if p == RDF['first']:
                firstNodes[s] = o
            elif p == RDF['rest']:
                restNodes[s] = o
            else:
                graphStmts.add((s, p, o))

        def gatherList(start):
            lst = []
            cur = start
            while cur != RDF['nil']:
                lst.append(firstNodes[cur])
                cur = restNodes[cur]
            return lst

        for s, p, o in graphStmts:
            subjList = objList = None
            if s in firstNodes:
                subjList = gatherList(s)
                s = None
            if o in firstNodes:
                objList = gatherList(o)
                o = None
            c = Chunk((s, p, o), subjList=subjList, objList=objList)

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

    def __bool__(self):
        return bool(self.chunksUsedByFuncs) or bool(self.staticChunks) or bool(self.patternChunks)

    def __repr__(self):
        return f'ChunkedGraph({self.__dict__})'

    def allChunks(self) -> Iterable[Chunk]:
        yield from itertools.chain(self.staticChunks, self.patternChunks, self.chunksUsedByFuncs)

    def __contains__(self, ch: Chunk) -> bool:
        return ch in self.allChunks()
