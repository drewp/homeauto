import itertools
import logging
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Set, Tuple, Type, Union, cast

from rdflib.graph import Graph
from rdflib.namespace import RDF
from rdflib.term import Literal, Node, URIRef, Variable

from candidate_binding import CandidateBinding
from inference_types import Inconsistent, RuleUnboundBnode, WorkingSetBnode

log = logging.getLogger('infer')

INDENT = '    '

ChunkPrimaryTriple = Tuple[Optional[Node], Node, Optional[Node]]


@dataclass
class AlignedRuleChunk:
    """a possible association between a rule chunk and a workingSet chunk. You can test
    whether the association would still be possible under various additional bindings."""
    ruleChunk: 'Chunk'
    workingSetChunk: 'Chunk'

    def __post_init__(self):
        if not self.matches():
            raise Inconsistent()

    def newBindingIfMatched(self, prevBindings: CandidateBinding) -> CandidateBinding:
        """supposing this rule did match the statement, what new bindings would
        that produce?

        raises Inconsistent if the existing bindings mean that our aligned
        chunks can no longer match.
        """
        outBinding = CandidateBinding({})
        for rt, ct in zip(self.ruleChunk._allTerms(), self.workingSetChunk._allTerms()):
            if isinstance(rt, (Variable, RuleUnboundBnode)):
                if prevBindings.contains(rt) and prevBindings.applyTerm(rt) != ct:
                    msg = f'{rt=} {ct=} {prevBindings=}' if log.isEnabledFor(logging.DEBUG) else ''
                    raise Inconsistent(msg)
                if outBinding.contains(rt) and outBinding.applyTerm(rt) != ct:
                    # maybe this can happen, for stmts like ?x :a ?x .
                    raise Inconsistent("outBinding inconsistent with itself")
                outBinding.addNewBindings(CandidateBinding({rt: ct}))
            else:
                if rt != ct:
                    # getting here means prevBindings was set to something our
                    # rule statement disagrees with.
                    raise Inconsistent(f'{rt=} != {ct=}')
        return outBinding

    def matches(self) -> bool:
        """could this rule, with its BindableTerm wildcards, match workingSetChunk?"""
        for selfTerm, otherTerm in zip(self.ruleChunk._allTerms(), self.workingSetChunk._allTerms()):
            if not isinstance(selfTerm, (Variable, RuleUnboundBnode)) and selfTerm != otherTerm:
                return False
        return True


@dataclass
class Chunk:  # rename this
    """A statement, maybe with variables in it, except *the subject or object
    can be rdf lists*. This is done to optimize list comparisons (a lot) at the
    very minor expense of not handling certain exotic cases, such as a branching
    list.

    Example: (?x ?y) math:sum ?z . <-- this becomes one Chunk.

    A function call in a rule is always contained in exactly one chunk.

    https://www.w3.org/TeamSubmission/n3/#:~:text=Implementations%20may%20treat%20list%20as%20a%20data%20type
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

    def __lt__(self, other):
        return self.sortKey < other.sortKey

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

    def ruleMatchesFrom(self, workingSet: 'ChunkedGraph') -> Iterator[AlignedRuleChunk]:
        """Chunks from workingSet where self, which may have BindableTerm wildcards, could match that workingSet Chunk."""
        # if log.isEnabledFor(logging.DEBUG):
        #     log.debug(f'{INDENT*6} computing {self}.ruleMatchesFrom({workingSet}')
        allChunksIter = workingSet.allChunks()
        if "stable failures please":
            allChunksIter = sorted(allChunksIter)
        for chunk in allChunksIter:
            try:
                aligned = AlignedRuleChunk(self, chunk)
            except Inconsistent:
                continue
            yield aligned

    def __repr__(self):
        pre = ('+'.join('%s' % elem for elem in self.subjList) + '+' if self.subjList else '')
        post = ('+' + '+'.join('%s' % elem for elem in self.objList) if self.objList else '')
        return pre + repr(self.primary) + post

    def isFunctionCall(self, functionsFor) -> bool:
        return bool(list(functionsFor(cast(URIRef, self.predicate))))

    def isStatic(self) -> bool:
        return all(_termIsStatic(s) for s in self._allTerms())

    def apply(self, cb: CandidateBinding) -> 'Chunk':
        """Chunk like this one but with cb substitutions applied. If the flag is
        True, we raise BindingUnknown instead of leaving a term unbound"""
        fn = lambda t: cb.applyTerm(t, failUnbound=False)
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


def applyChunky(cb: CandidateBinding,
                g: Iterable[AlignedRuleChunk]) -> Iterator[AlignedRuleChunk]:
    for aligned in g:
        bound = aligned.ruleChunk.apply(cb)
        try:
            yield AlignedRuleChunk(bound, aligned.workingSetChunk)
        except Inconsistent:
            pass


class ChunkedGraph:
    """a Graph converts 1-to-1 with a ChunkedGraph, where the Chunks have
    combined some statements together. (The only exception is that bnodes for
    rdf lists are lost)"""

    def __init__(
            self,
            graph: Graph,
            bnodeType: Union[Type[RuleUnboundBnode], Type[WorkingSetBnode]],
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
            from rdflib import BNode
            if isinstance(s, BNode): s = bnodeType(s)
            if isinstance(p, BNode): p = bnodeType(p)
            if isinstance(o, BNode): o = bnodeType(o)

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
