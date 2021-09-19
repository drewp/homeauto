"""
copied from reasoning 2021-08-29. probably same api. should
be able to lib/ this out
"""
import itertools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, Union, cast

from prometheus_client import Histogram, Summary
from rdflib import RDF, BNode, Graph, Namespace
from rdflib.graph import ConjunctiveGraph
from rdflib.term import Node, URIRef, Variable

from candidate_binding import BindingConflict, CandidateBinding
from inference_types import BindingUnknown, Inconsistent, Triple
from lhs_evaluation import functionsFor
from rdf_debug import graphDump
from stmt_chunk import Chunk, ChunkedGraph, applyChunky

log = logging.getLogger('infer')
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

    This iterator is restartable."""
    lhsChunk: Chunk
    prev: Optional['ChunkLooper']
    workingSet: 'ChunkedGraph'
    parent: 'Lhs'  # just for lhs.graph, really

    def __repr__(self):
        return f'{self.__class__.__name__}{self._shortId}{"<pastEnd>" if self.pastEnd() else ""}'

    def __post_init__(self):
        self._shortId = next(_chunkLooperShortId)
        self._myWorkingSetMatches = self.lhsChunk.myMatches(self.workingSet)

        self._current = CandidateBinding({})
        self._pastEnd = False
        self._seenBindings: List[CandidateBinding] = []

        log.debug(f'{INDENT*6} introducing {self!r}({self.lhsChunk}, {self._myWorkingSetMatches=})')

        self.restart()

    def _prevBindings(self) -> CandidateBinding:
        if not self.prev or self.prev.pastEnd():
            return CandidateBinding({})

        return self.prev.currentBinding()

    def advance(self):
        """update to a new set of bindings we haven't seen (since last restart), or go into pastEnd mode"""
        if self._pastEnd:
            raise NotImplementedError('need restart')
        log.debug('')
        augmentedWorkingSet: Sequence[Chunk] = []
        if self.prev is None:
            augmentedWorkingSet = self._myWorkingSetMatches
        else:
            augmentedWorkingSet = list(
                applyChunky(self.prev.currentBinding(), self._myWorkingSetMatches, returnBoundStatementsOnly=False))

        log.debug(f'{INDENT*6} --> {self}.advance has {augmentedWorkingSet=} {self._current=}')

        if self._advanceWithPlainMatches(augmentedWorkingSet):
            log.debug(f'{INDENT*6} <-- {self}.advance finished with plain matches')
            return

        if self._advanceWithFunctions():
            log.debug(f'{INDENT*6} <-- {self}.advance finished with function matches')
            return

        log.debug(f'{INDENT*6} <-- {self}.advance had nothing and is now past end')
        self._pastEnd = True

    def _advanceWithPlainMatches(self, augmentedWorkingSet: Sequence[Chunk]) -> bool:
        log.debug(f'{INDENT*7} {self} mines {len(augmentedWorkingSet)} matching augmented statements')
        for s in augmentedWorkingSet:
            log.debug(f'{INDENT*7} {s}')

        for chunk in augmentedWorkingSet:
            try:
                outBinding = self.lhsChunk.totalBindingIfThisStmtWereTrue(self._prevBindings(), chunk)
            except Inconsistent:
                log.debug(f'{INDENT*7} ChunkLooper{self._shortId} - {chunk} would be inconsistent with prev bindings')
                continue

            log.debug(f'{INDENT*7} {outBinding=} {self._seenBindings=}')
            if outBinding not in self._seenBindings:
                self._seenBindings.append(outBinding.copy())
                self._current = outBinding
                log.debug(f'{INDENT*7} new binding from {self} -> {outBinding}')
                return True
        return False

    def _advanceWithFunctions(self) -> bool:
        pred: Node = self.lhsChunk.predicate
        if not isinstance(pred, URIRef):
            raise NotImplementedError

        log.debug(f'{INDENT*6} advanceWithFunctions {pred}')

        for functionType in functionsFor(pred):
            fn = functionType(self.lhsChunk, self.parent.graph)
            log.debug(f'{INDENT*7} ChunkLooper{self._shortId} advanceWithFunctions, {functionType=}')

            try:

                out = fn.bind(self._prevBindings())
            except BindingUnknown:
                pass
            else:
                if out is not None:
                    binding: CandidateBinding = self._prevBindings().copy()
                    binding.addNewBindings(out)
                    if binding not in self._seenBindings:
                        self._seenBindings.append(binding)
                        self._current = binding
                        log.debug(f'{INDENT*7} new binding from {self} -> {binding}')
                        return True

        return False

    def _boundOperands(self, operands) -> List[Node]:
        pb: CandidateBinding = self._prevBindings()

        boundOperands: List[Node] = []
        for op in operands:
            if isinstance(op, (Variable, BNode)):
                boundOperands.append(pb.applyTerm(op))
            else:
                boundOperands.append(op)
        return boundOperands

    def currentBinding(self) -> CandidateBinding:
        if self.pastEnd():
            raise NotImplementedError()
        return self._current

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
        """bindings that fit the LHS of a rule, using statements from workingSet and functions
        from LHS"""
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

        if not self.graph.patternChunks:
            # static only
            yield BoundLhs(self, CandidateBinding({}))
            return

        log.debug(f'{INDENT*4} build new ChunkLooper stack')

        try:
            chunkStack = self._assembleRings(knownTrue, stats)
        except NoOptions:
            log.debug(f'{INDENT*5} start up with no options; 0 bindings')
            return
        self._debugChunkStack('initial odometer', chunkStack)
        self._assertAllRingsAreValid(chunkStack)

        lastRing = chunkStack[-1]
        iterCount = 0
        while True:
            iterCount += 1
            if iterCount > ruleStatementsIterationLimit:
                raise ValueError('rule too complex')

            log.debug(f'{INDENT*4} vv findCandBindings iteration {iterCount}')

            yield BoundLhs(self, lastRing.currentBinding())

            self._debugChunkStack('odometer', chunkStack)

            done = self._advanceAll(chunkStack)

            self._debugChunkStack(f'odometer after ({done=})', chunkStack)

            log.debug(f'{INDENT*4} ^^ findCandBindings iteration done')
            if done:
                break

    def _debugChunkStack(self, label: str, chunkStack: List[ChunkLooper]):
        log.debug(f'{INDENT*5} {label}:')
        for i, l in enumerate(chunkStack):
            log.debug(f'{INDENT*6} [{i}] {l} curbind={l.currentBinding() if not l.pastEnd() else "<end>"}')

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

        log.info(f'{INDENT*2} stats={dict(stats)}')
        log.info(f'{INDENT*2} taking permutations of {len(self.graph.patternChunks)=}')
        for i, perm in enumerate(itertools.permutations(self.graph.patternChunks)):
            stmtStack: List[ChunkLooper] = []
            prev: Optional[ChunkLooper] = None
            if log.isEnabledFor(logging.DEBUG):
                log.debug(f'{INDENT*5} [perm {i}] try stmts in this order: {" -> ".join(repr(p) for p in perm)}')

            for s in perm:
                try:
                    elem = ChunkLooper(s, prev, knownTrue, parent=self)
                except NoOptions:
                    log.debug(f'{INDENT*6} permutation didnt work, try another')
                    break
                stmtStack.append(elem)
                prev = stmtStack[-1]
            else:
                return stmtStack
            if i > 5000:
                raise NotImplementedError(f'trying too many permutations {len(chunks)=}')

        log.debug(f'{INDENT*6} no perms worked- rule cannot match anything')
        raise NoOptions()

    def _advanceAll(self, stmtStack: List[ChunkLooper]) -> bool:
        carry = True  # 1st elem always must advance
        for i, ring in enumerate(stmtStack):
            # unlike normal odometer, advancing any earlier ring could invalidate later ones
            if carry:
                log.debug(f'{INDENT*5} advanceAll [{i}] {ring} carry/advance')
                ring.advance()
                carry = False
            if ring.pastEnd():
                if ring is stmtStack[-1]:
                    log.debug(f'{INDENT*5} advanceAll [{i}] {ring} says we done')
                    return True
                log.debug(f'{INDENT*5} advanceAll [{i}] {ring} restart')
                ring.restart()
                carry = True
        return False

    def _assertAllRingsAreValid(self, stmtStack):
        if any(ring.pastEnd() for ring in stmtStack):  # this is an unexpected debug assertion
            log.debug(f'{INDENT*5} some rings started at pastEnd {stmtStack}')
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
        self.lhs = Lhs(ChunkedGraph(self.lhsGraph, functionsFor))
        #
        self.rhsBnodeMap = {}

    def applyRule(self, workingSet: Graph, implied: Graph, stats: Dict, ruleStatementsIterationLimit):
        # this does not change for the current applyRule call. The rule will be
        # tried again in an outer loop, in case it can produce more.
        workingSetChunked = ChunkedGraph(workingSet, functionsFor)

        for bound in self.lhs.findCandidateBindings(workingSetChunked, stats, ruleStatementsIterationLimit):
            log.debug(f'{INDENT*5} +rule has a working binding: {bound}')

            # rhs could have more bnodes, and they just need to be distinct per rule-firing that we do
            existingRhsBnodes = set()
            for stmt in self.rhsGraph:
                for t in stmt:
                    if isinstance(t, BNode):
                        existingRhsBnodes.add(t)
            # if existingRhsBnodes:
            # log.debug(f'{INDENT*6} mapping rhs bnodes {existingRhsBnodes} to new ones')

            for b in existingRhsBnodes:

                key = tuple(sorted(bound.binding.binding.items())), b
                self.rhsBnodeMap.setdefault(key, BNode())
                try:
                    bound.binding.addNewBindings(CandidateBinding({b: self.rhsBnodeMap[key]}))
                except BindingConflict:
                    continue

            # for lhsBoundStmt in bound.binding.apply(bound.lhsStmtsWithoutEvals()):
            #     log.debug(f'{INDENT*6} adding to workingSet {lhsBoundStmt=}')
            #     workingSet.add(lhsBoundStmt)
            # log.debug(f'{INDENT*6} rhsGraph is good: {list(self.rhsGraph)}')

            for newStmt in bound.binding.apply(self.rhsGraph):
                # log.debug(f'{INDENT*6} adding {newStmt=}')
                workingSet.add(newStmt)
                implied.add(newStmt)


@dataclass
class Inference:
    rulesIterationLimit = 3
    ruleStatementsIterationLimit = 3

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
        while delta > 0 and rulesIterations <= self.rulesIterationLimit:
            log.debug('')
            log.info(f'{INDENT*1}*iteration {rulesIterations}')

            delta = -len(implied)
            self._iterateAllRules(workingSet, implied, stats)
            delta += len(implied)
            rulesIterations += 1
            log.info(f'{INDENT*2} this inference iteration added {delta} more implied stmts')
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
        for stmt in sorted(r.lhsGraph, reverse=True):
            log.debug(f'{INDENT*4} {stmt}')
        log.debug(f'{INDENT*3} rule def rhs: {graphDump(r.rhsGraph)}')
