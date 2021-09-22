"""
copied from reasoning 2021-08-29. probably same api. should
be able to lib/ this out
"""
import itertools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Union, cast

from prometheus_client import Histogram, Summary
from rdflib import Graph, Namespace
from rdflib.graph import ConjunctiveGraph
from rdflib.term import Node, URIRef, Variable

from candidate_binding import BindingConflict, CandidateBinding
from inference_types import (BindingUnknown, Inconsistent, RhsBnode, RuleOutBnode, RuleUnboundBnode, Triple, WorkingSetBnode)
from lhs_evaluation import functionsFor
from rdf_debug import graphDump
from stmt_chunk import AlignedRuleChunk, Chunk, ChunkedGraph, applyChunky

log = logging.getLogger('infer')
odolog = logging.getLogger('infer.odo')  # the "odometer" logic
ringlog = logging.getLogger('infer.ring')  # for ChunkLooper

INDENT = '    '

INFER_CALLS = Summary('inference_infer_calls', 'calls')
INFER_GRAPH_SIZE = Histogram('inference_graph_size', 'statements', buckets=[2**x for x in range(2, 20, 2)])

ROOM = Namespace("http://projects.bigasterisk.com/room/")
LOG = Namespace('http://www.w3.org/2000/10/swap/log#')
MATH = Namespace('http://www.w3.org/2000/10/swap/math#')


class NoOptions(ValueError):
    """ChunkLooper has no possibilites to add to the binding; the whole rule must therefore not apply"""


_chunkLooperShortId = itertools.count()


@dataclass
class ChunkLooper:
    """given one LHS Chunk, iterate through the possible matches for it,
    returning what bindings they would imply. Only distinct bindings are
    returned. The bindings build on any `prev` ChunkLooper's results.

    In the odometer metaphor used below, this is one of the rings.

    This iterator is restartable."""
    lhsChunk: Chunk
    prev: Optional['ChunkLooper']
    workingSet: 'ChunkedGraph'

    def __repr__(self):
        return f'{self.__class__.__name__}{self._shortId}{"<pastEnd>" if self.pastEnd() else ""}'

    def __post_init__(self):
        self._shortId = next(_chunkLooperShortId)
        self._alignedMatches = list(self.lhsChunk.ruleMatchesFrom(self.workingSet))

        # only ours- do not store prev, since it could change without us
        self._current = CandidateBinding({})
        self._pastEnd = False
        self._seenBindings: List[CandidateBinding] = []  # combined bindings (up to our ring) that we've returned

        if ringlog.isEnabledFor(logging.DEBUG):
            ringlog.debug('')
            ringlog.debug(f'{INDENT*6} introducing {self!r}({self.lhsChunk}, {self._alignedMatches=})')

        self.restart()

    def _prevBindings(self) -> CandidateBinding:
        if not self.prev or self.prev.pastEnd():
            return CandidateBinding({})

        return self.prev.currentBinding()

    def advance(self):
        """update _current to a new set of valid bindings we haven't seen (since
        last restart), or go into pastEnd mode. Note that _current is just our
        contribution, but returned valid bindings include all prev rings."""
        if self._pastEnd:
            raise NotImplementedError('need restart')
        ringlog.debug('')
        augmentedWorkingSet: List[AlignedRuleChunk] = []
        if self.prev is None:
            augmentedWorkingSet = self._alignedMatches
        else:
            augmentedWorkingSet = list(applyChunky(self.prev.currentBinding(), self._alignedMatches))

        if self._advanceWithPlainMatches(augmentedWorkingSet):
            ringlog.debug(f'{INDENT*6} <-- {self}.advance finished with plain matches')
            return

        if self._advanceWithFunctions():
            ringlog.debug(f'{INDENT*6} <-- {self}.advance finished with function matches')
            return

        ringlog.debug(f'{INDENT*6} <-- {self}.advance had nothing and is now past end')
        self._pastEnd = True

    def _advanceWithPlainMatches(self, augmentedWorkingSet: List[AlignedRuleChunk]) -> bool:
        ringlog.debug(f'{INDENT*7} {self} mines {len(augmentedWorkingSet)} matching augmented statements')
        for s in augmentedWorkingSet:
            ringlog.debug(f'{INDENT*8} {s}')

        for aligned in augmentedWorkingSet:
            try:
                newBinding = aligned.newBindingIfMatched(self._prevBindings())
            except Inconsistent as exc:
                ringlog.debug(
                    f'{INDENT*7} ChunkLooper{self._shortId} - {aligned} would be inconsistent with prev bindings ({exc})')
                continue

            if self._testAndKeepNewBinding(newBinding):
                return True
        return False

    def _advanceWithFunctions(self) -> bool:
        pred: Node = self.lhsChunk.predicate
        if not isinstance(pred, URIRef):
            raise NotImplementedError

        ringlog.debug(f'{INDENT*6} advanceWithFunctions {pred!r}')

        for functionType in functionsFor(pred):
            fn = functionType(self.lhsChunk)
            ringlog.debug(f'{INDENT*7} ChunkLooper{self._shortId} advanceWithFunctions, {functionType=}')

            try:

                newBinding = fn.bind(self._prevBindings())
            except BindingUnknown:
                pass
            else:
                if newBinding is not None:
                    if self._testAndKeepNewBinding(newBinding):
                        return True

        return False

    def _testAndKeepNewBinding(self, newBinding):
        fullBinding: CandidateBinding = self._prevBindings().copy()
        fullBinding.addNewBindings(newBinding)
        isNew = fullBinding not in self._seenBindings
        ringlog.debug(f'{INDENT*7} {self} considering {newBinding=} to make {fullBinding}. {isNew=}')
        if isNew:
            self._seenBindings.append(fullBinding.copy())
            self._current = newBinding
            return True
        return False

    def _boundOperands(self, operands) -> List[Node]:
        pb: CandidateBinding = self._prevBindings()

        boundOperands: List[Node] = []
        for op in operands:
            if isinstance(op, (Variable, RuleUnboundBnode)):
                boundOperands.append(pb.applyTerm(op))
            else:
                boundOperands.append(op)
        return boundOperands

    def currentBinding(self) -> CandidateBinding:
        if self.pastEnd():
            raise NotImplementedError()
        together = self._prevBindings().copy()
        together.addNewBindings(self._current)
        return together

    def pastEnd(self) -> bool:
        return self._pastEnd

    def restart(self):
        self._pastEnd = False
        self._seenBindings = []
        self.advance()
        if self.pastEnd():
            raise NoOptions()


@dataclass
class Lhs:
    graph: ChunkedGraph  # our full LHS graph, as input. See below for the statements partitioned into groups.

    def __post_init__(self):

        self.myPreds = self.graph.allPredicatesExceptFunctions()

    def __repr__(self):
        return f"Lhs({self.graph!r})"

    def findCandidateBindings(self, knownTrue: ChunkedGraph, stats, ruleStatementsIterationLimit) -> Iterator['BoundLhs']:
        """distinct bindings that fit the LHS of a rule, using statements from
        workingSet and functions from LHS"""
        if not self.graph:
            # special case- no LHS!
            yield BoundLhs(self, CandidateBinding({}))
            return

        if self._checkPredicateCounts(knownTrue):
            stats['_checkPredicateCountsCulls'] += 1
            return

        if not all(ch in knownTrue for ch in self.graph.staticChunks):
            stats['staticStmtCulls'] += 1
            return
        # After this point we don't need to consider self.graph.staticChunks.

        if not self.graph.patternChunks and not self.graph.chunksUsedByFuncs:
            # static only
            yield BoundLhs(self, CandidateBinding({}))
            return

        log.debug('')
        try:
            chunkStack = self._assembleRings(knownTrue, stats)
        except NoOptions:
            ringlog.debug(f'{INDENT*5} start up with no options; 0 bindings')
            return
        self._debugChunkStack('time to spin: initial odometer is', chunkStack)
        self._assertAllRingsAreValid(chunkStack)

        lastRing = chunkStack[-1]
        iterCount = 0
        while True:
            iterCount += 1
            if iterCount > ruleStatementsIterationLimit:
                raise ValueError('rule too complex')

            log.debug(f'{INDENT*4} vv findCandBindings iteration {iterCount}')

            yield BoundLhs(self, lastRing.currentBinding())

            # self._debugChunkStack('odometer', chunkStack)

            done = self._advanceTheStack(chunkStack)

            self._debugChunkStack(f'odometer after ({done=})', chunkStack)

            log.debug(f'{INDENT*4} ^^ findCandBindings iteration done')
            if done:
                break

    def _debugChunkStack(self, label: str, chunkStack: List[ChunkLooper]):
        odolog.debug(f'{INDENT*4} {label}:')
        for i, l in enumerate(chunkStack):
            odolog.debug(f'{INDENT*5} [{i}] {l} curbind={l.currentBinding() if not l.pastEnd() else "<end>"}')

    def _checkPredicateCounts(self, knownTrue):
        """raise NoOptions quickly in some cases"""

        if self.graph.noPredicatesAppear(self.myPreds):
            log.debug(f'{INDENT*3} checkPredicateCounts does cull because not all {self.myPreds=} are in knownTrue')
            return True
        log.debug(f'{INDENT*3} checkPredicateCounts does not cull because all {self.myPreds=} are in knownTrue')
        return False

    def _assembleRings(self, knownTrue: ChunkedGraph, stats) -> List[ChunkLooper]:
        """make ChunkLooper for each stmt in our LHS graph, but do it in a way that they all
        start out valid (or else raise NoOptions). static chunks have already been confirmed."""

        log.debug(f'{INDENT*4} stats={dict(stats)}')
        odolog.debug(f'{INDENT*3} build new ChunkLooper stack')
        chunks = list(self.graph.patternChunks.union(self.graph.chunksUsedByFuncs))
        chunks.sort(key=None)
        odolog.info(f' {INDENT*3} taking permutations of {len(chunks)=}')
        for i, perm in enumerate(itertools.permutations(chunks)):
            looperRings: List[ChunkLooper] = []
            prev: Optional[ChunkLooper] = None
            if odolog.isEnabledFor(logging.DEBUG):
                odolog.debug(f'{INDENT*4} [perm {i}] try rule chunks in this order: {"  THEN  ".join(repr(p) for p in perm)}')

            for ruleChunk in perm:
                try:
                    # These are getting rebuilt a lot which takes time. It would
                    # be nice if they could accept a changing `prev` order
                    # (which might already be ok).
                    looper = ChunkLooper(ruleChunk, prev, knownTrue)
                except NoOptions:
                    odolog.debug(f'{INDENT*5} permutation didnt work, try another')
                    break
                looperRings.append(looper)
                prev = looperRings[-1]
            else:
                # bug: At this point we've only shown that these are valid
                # starting rings. The rules might be tricky enough that this
                # permutation won't get us to the solution.
                return looperRings
            if i > 50000:
                raise NotImplementedError(f'trying too many permutations {len(chunks)=}')

        odolog.debug(f'{INDENT*5} no perms worked- rule cannot match anything')
        raise NoOptions()

    def _advanceTheStack(self, looperRings: List[ChunkLooper]) -> bool:
        carry = True  # last elem always must advance
        for i, ring in reversed(list(enumerate(looperRings))):
            # unlike normal odometer, advancing any earlier ring could invalidate later ones
            if carry:
                odolog.debug(f'{INDENT*4} advanceAll [{i}] {ring} carry/advance')
                ring.advance()
                carry = False
            if ring.pastEnd():
                if ring is looperRings[0]:
                    allRingsDone = [r.pastEnd() for r in looperRings]
                    odolog.debug(f'{INDENT*4} advanceAll [{i}] {ring} says we done   {allRingsDone=}')
                    return True
                odolog.debug(f'{INDENT*4} advanceAll [{i}] {ring} restart')
                ring.restart()
                carry = True
        return False

    def _assertAllRingsAreValid(self, looperRings):
        if any(ring.pastEnd() for ring in looperRings):  # this is an unexpected debug assertion
            odolog.warning(f'{INDENT*4} some rings started at pastEnd {looperRings}')
            raise NoOptions()


@dataclass
class BoundLhs:
    lhs: Lhs
    binding: CandidateBinding


@dataclass
class Rule:
    lhsGraph: Graph
    rhsGraph: Graph

    def __post_init__(self):
        self.lhs = Lhs(ChunkedGraph(self.lhsGraph, RuleUnboundBnode, functionsFor))

        self.maps = {}

        self.rhsGraphConvert: List[Triple] = []
        for s, p, o in self.rhsGraph:
            from rdflib import BNode
            if isinstance(s, BNode):
                s = RhsBnode(s)
            if isinstance(p, BNode):
                p = RhsBnode(p)
            if isinstance(o, BNode):
                o = RhsBnode(o)
            self.rhsGraphConvert.append((s, p, o))

    def applyRule(self, workingSet: Graph, implied: Graph, stats: Dict, ruleStatementsIterationLimit):
        # this does not change for the current applyRule call. The rule will be
        # tried again in an outer loop, in case it can produce more.
        workingSetChunked = ChunkedGraph(workingSet, WorkingSetBnode, functionsFor)

        for bound in self.lhs.findCandidateBindings(workingSetChunked, stats, ruleStatementsIterationLimit):
            log.debug(f'{INDENT*5} +rule has a working binding: {bound}')

            newStmts = self.generateImpliedFromRhs(bound.binding)

            for newStmt in newStmts:
                # log.debug(f'{INDENT*6} adding {newStmt=}')
                workingSet.add(newStmt)
                implied.add(newStmt)

    def generateImpliedFromRhs(self, binding: CandidateBinding) -> List[Triple]:

        out: List[Triple] = []

        # Each time the RHS is used (in a rule firing), its own BNodes (which
        # are subtype RhsBnode) need to be turned into distinct ones. Note that
        # bnodes that come from the working set should not be remapped.
        rhsBnodeMap: Dict[RhsBnode, WorkingSetBnode] = {}

        # but, the iteration loop could come back with the same bindings again
        key = binding.key()
        rhsBnodeMap = self.maps.setdefault(key, {})

        for stmt in binding.apply(self.rhsGraphConvert):

            outStmt: List[Node] = []

            for t in stmt:
                if isinstance(t, RhsBnode):
                    if t not in rhsBnodeMap:
                        rhsBnodeMap[t] = WorkingSetBnode()
                    t = rhsBnodeMap[t]

                outStmt.append(t)

            log.debug(f'{INDENT*6} rhs stmt {stmt} became {outStmt}')
            out.append((outStmt[0], outStmt[1], outStmt[2]))

        return out


@dataclass
class Inference:
    rulesIterationLimit = 4
    ruleStatementsIterationLimit = 5000

    def __init__(self) -> None:
        self.rules: List[Rule] = []
        self._nonRuleStmts: List[Triple] = []

    def setRules(self, g: ConjunctiveGraph):
        self.rules = []
        self._nonRuleStmts = []
        for stmt in g:
            if stmt[1] == LOG['implies']:
                self.rules.append(Rule(stmt[0], stmt[2]))
            else:
                self._nonRuleStmts.append(stmt)

    def nonRuleStatements(self) -> List[Triple]:
        return self._nonRuleStmts

    @INFER_CALLS.time()
    def infer(self, graph: Graph):
        """
        returns new graph of inferred statements.
        """
        n = graph.__len__()
        INFER_GRAPH_SIZE.observe(n)
        log.info(f'{INDENT*0} Begin inference of graph len={n} with rules len={len(self.rules)}:')
        startTime = time.time()
        stats: Dict[str, Union[int, float]] = defaultdict(lambda: 0)

        # everything that is true: the input graph, plus every rule conclusion we can make
        workingSet = Graph()
        workingSet += self._nonRuleStmts
        workingSet += graph

        # just the statements that came from RHS's of rules that fired.
        implied = ConjunctiveGraph()

        rulesIterations = 0
        delta = 1
        stats['initWorkingSet'] = cast(int, workingSet.__len__())
        while delta > 0:
            log.debug('')
            log.info(f'{INDENT*1}*iteration {rulesIterations}')

            delta = -len(implied)
            self._iterateAllRules(workingSet, implied, stats)
            delta += len(implied)
            rulesIterations += 1
            log.info(f'{INDENT*2} this inference iteration added {delta} more implied stmts')
            if rulesIterations >= self.rulesIterationLimit:
                raise ValueError(f"rule too complex after {rulesIterations=}")
        stats['iterations'] = rulesIterations
        stats['timeSpent'] = round(time.time() - startTime, 3)
        stats['impliedStmts'] = len(implied)
        log.info(f'{INDENT*0} Inference done {dict(stats)}.')
        log.debug('Implied:')
        log.debug(graphDump(implied))
        return implied

    def _iterateAllRules(self, workingSet: Graph, implied: Graph, stats):
        for i, rule in enumerate(self.rules):
            self._logRuleApplicationHeader(workingSet, i, rule)
            rule.applyRule(workingSet, implied, stats, self.ruleStatementsIterationLimit)

    def _logRuleApplicationHeader(self, workingSet, i, r: Rule):
        if not log.isEnabledFor(logging.DEBUG):
            return

        log.debug('')
        log.debug(f'{INDENT*2} workingSet:')
        # for j, stmt in enumerate(sorted(workingSet)):
        #     log.debug(f'{INDENT*3} ({j}) {stmt}')
        log.debug(f'{INDENT*3} {graphDump(workingSet, oneLine=False)}')

        log.debug('')
        log.debug(f'{INDENT*2}-applying rule {i}')
        log.debug(f'{INDENT*3} rule def lhs:')
        for stmt in sorted(r.lhs.graph.allChunks()):
            log.debug(f'{INDENT*4} {stmt}')
        log.debug(f'{INDENT*3} rule def rhs: {graphDump(r.rhsGraph)}')
