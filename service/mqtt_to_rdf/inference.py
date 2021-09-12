"""
copied from reasoning 2021-08-29. probably same api. should
be able to lib/ this out
"""
import itertools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Set, Tuple, Union, cast

from prometheus_client import Histogram, Summary
from rdflib import BNode, Graph, Namespace
from rdflib.graph import ConjunctiveGraph, ReadOnlyGraphAggregate
from rdflib.term import Literal, Node, Variable

from candidate_binding import CandidateBinding
from inference_types import (BindableTerm, EvaluationFailed, ReadOnlyWorkingSet, Triple)
from lhs_evaluation import Decimal, Evaluation, numericNode

log = logging.getLogger('infer')
INDENT = '    '

INFER_CALLS = Summary('inference_infer_calls', 'calls')
INFER_GRAPH_SIZE = Histogram('inference_graph_size', 'statements', buckets=[2**x for x in range(2, 20, 2)])

ROOM = Namespace("http://projects.bigasterisk.com/room/")
LOG = Namespace('http://www.w3.org/2000/10/swap/log#')
MATH = Namespace('http://www.w3.org/2000/10/swap/math#')


def stmtTemplate(stmt: Triple) -> Tuple[Optional[Node], Optional[Node], Optional[Node]]:
    return (
        None if isinstance(stmt[0], (Variable, BNode)) else stmt[0],
        None if isinstance(stmt[1], (Variable, BNode)) else stmt[1],
        None if isinstance(stmt[2], (Variable, BNode)) else stmt[2],
    )


class NoOptions(ValueError):
    """stmtlooper has no possibilites to add to the binding; the whole rule must therefore not apply"""


class Inconsistent(ValueError):
    """adding this stmt would be inconsistent with an existing binding"""


@dataclass
class StmtLooper:
    lhsStmt: Triple
    prev: Optional['StmtLooper']
    workingSet: ReadOnlyWorkingSet

    def __repr__(self):
        return f'StmtLooper({graphDump([self.lhsStmt])} {"<pastEnd>" if self.pastEnd() else ""})'

    def __post_init__(self):
        self._myWorkingSetMatches = self._myMatches(self.workingSet)

        self._current = CandidateBinding({})
        self._pastEnd = False
        self._seenBindings: List[Dict[BindableTerm, Node]] = []
        self.restart()

    def _myMatches(self, g: Graph) -> List[Triple]:
        template = stmtTemplate(self.lhsStmt)

        stmts = sorted(cast(Iterator[Triple], list(g.triples(template))))
        # plus new lhs possibilties...
        # log.debug(f'{INDENT*6} {self} find {len(stmts)=} in {len(self.workingSet)=}')

        return stmts

    def _prevBindings(self) -> Dict[BindableTerm, Node]:
        if not self.prev or self.prev.pastEnd():
            return {}

        return self.prev.currentBinding().binding

    def advance(self):
        """update to a new set of bindings we haven't seen (since last restart), or go into pastEnd mode"""
        log.debug(f'{INDENT*6} {self} mines {len(self._myWorkingSetMatches)} matching statements')
        for i, stmt in enumerate(self._myWorkingSetMatches):
            try:
                outBinding = self._totalBindingIfThisStmtWereTrue(stmt)
            except Inconsistent:
                log.debug(f'{INDENT*7} {self} - {stmt} would be inconsistent with prev bindings')
                continue
            log.debug(f'seen {outBinding.binding} in {self._seenBindings}')
            if outBinding.binding not in self._seenBindings:
                self._seenBindings.append(outBinding.binding.copy())
                log.debug(f'no, adding')
                self._current = outBinding
                log.debug(f'{INDENT*7} {self} - Looper matches {stmt} which tells us {outBinding}')
                return
            log.debug(f'yes we saw')

        log.debug(f'{INDENT*6} {self} mines rules')

        if self.lhsStmt[1] == ROOM['asFarenheit']:
            pb: Dict[BindableTerm, Node] = self._prevBindings()
            if self.lhsStmt[0] in pb:
                operands = [pb[cast(BindableTerm, self.lhsStmt[0])]]
                f = cast(Literal, Literal(Decimal(numericNode(operands[0])) * 9 / 5 + 32))
                objVar = self.lhsStmt[2]
                if not isinstance(objVar, Variable):
                    raise TypeError(f'expected Variable, got {objVar!r}')
                newBindings = {cast(BindableTerm, objVar): cast(Node, f)}
                self._current.addNewBindings(CandidateBinding(newBindings))
                if newBindings not in self._seenBindings:
                    self._seenBindings.append(newBindings)
                    self._current = CandidateBinding(newBindings)

        log.debug(f'{INDENT*6} {self} is past end')
        self._pastEnd = True

    def _totalBindingIfThisStmtWereTrue(self, newStmt: Triple) -> CandidateBinding:
        outBinding = self._prevBindings().copy()
        for rt, ct in zip(self.lhsStmt, newStmt):
            if isinstance(rt, (Variable, BNode)):
                if rt in outBinding and outBinding[rt] != ct:
                    raise Inconsistent()
                outBinding[rt] = ct
        return CandidateBinding(outBinding)

    def currentBinding(self) -> CandidateBinding:
        if self.pastEnd():
            raise NotImplementedError()
        return self._current

    def newLhsStmts(self) -> List[Triple]:
        """under the curent bindings, what new stmts beyond workingSet are also true? includes all `prev`"""
        return []

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
    graph: Graph

    def __post_init__(self):
        # do precomputation in here that's not specific to the workingSet
        # self.staticRuleStmts = Graph()
        # self.nonStaticRuleStmts = Graph()

        # self.lhsBindables: Set[BindableTerm] = set()
        # self.lhsBnodes: Set[BNode] = set()
        # for ruleStmt in self.graph:
        #     varsAndBnodesInStmt = [term for term in ruleStmt if isinstance(term, (Variable, BNode))]
        #     self.lhsBindables.update(varsAndBnodesInStmt)
        #     self.lhsBnodes.update(x for x in varsAndBnodesInStmt if isinstance(x, BNode))
        #     if not varsAndBnodesInStmt:
        #         self.staticRuleStmts.add(ruleStmt)
        #     else:
        #         self.nonStaticRuleStmts.add(ruleStmt)

        # self.nonStaticRuleStmtsSet = set(self.nonStaticRuleStmts)

        self.evaluations = list(Evaluation.findEvals(self.graph))

    def __repr__(self):
        return f"Lhs({graphDump(self.graph)})"

    def findCandidateBindings(self, knownTrue: ReadOnlyWorkingSet, stats) -> Iterator['BoundLhs']:
        """bindings that fit the LHS of a rule, using statements from workingSet and functions
        from LHS"""
        log.debug(f'{INDENT*4} build new StmtLooper stack')

        stmtStack: List[StmtLooper] = []
        try:
            prev: Optional[StmtLooper] = None
            for s in sorted(self.graph):  # order of this matters! :(
                stmtStack.append(StmtLooper(s, prev, knownTrue))
                prev = stmtStack[-1]
        except NoOptions:
            log.debug(f'{INDENT*5} no options; 0 bindings')
            return

        log.debug(f'{INDENT*5} initial odometer:')
        for l in stmtStack:
            log.debug(f'{INDENT*6} {l}')

        if any(ring.pastEnd() for ring in stmtStack):
            log.debug(f'{INDENT*5} some rings started at pastEnd {stmtStack}')

            raise NoOptions()
        sl = stmtStack[-1]
        iterCount = 0
        while True:
            iterCount += 1
            if iterCount > 10:
                raise ValueError('stuck')

            log.debug(f'{INDENT*4} vv findCandBindings iteration {iterCount}')

            log.debug(f'{INDENT*5} <<<')
            yield BoundLhs(self, sl.currentBinding())
            log.debug(f'{INDENT*5} >>>')

            log.debug(f'{INDENT*5} odometer:')
            for l in stmtStack:
                log.debug(f'{INDENT*6} {l} curbind={l.currentBinding() if not l.pastEnd() else "<end>"}')

            done = self._advanceAll(stmtStack)

            log.debug(f'{INDENT*5} odometer after ({done=}):')
            for l in stmtStack:
                log.debug(f'{INDENT*6} {l} curbind={l.currentBinding() if not l.pastEnd() else "<end>"}')

            log.debug(f'{INDENT*4} ^^ findCandBindings iteration done')
            if done:
                break

    def _advanceAll(self, stmtStack: List[StmtLooper]) -> bool:
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

    def _allStaticStatementsMatch(self, knownTrue: ReadOnlyWorkingSet) -> bool:
        # bug: see TestSelfFulfillingRule.test3 for a case where this rule's
        # static stmt is matched by a non-static stmt in the rule itself
        for ruleStmt in self.staticRuleStmts:
            if ruleStmt not in knownTrue:
                log.debug(f'{INDENT*3} {ruleStmt} not in working set- skip rule')
                return False
        return True

    def _possibleBindings(self, workingSet, stats) -> Iterator['BoundLhs']:
        """this yields at least the working bindings, and possibly others"""
        candidateTermMatches: Dict[BindableTerm, Set[Node]] = self._allCandidateTermMatches(workingSet)
        for bindRow in self._product(candidateTermMatches):
            try:
                yield BoundLhs(self, bindRow)
            except EvaluationFailed:
                stats['permCountFailingEval'] += 1

    def _allCandidateTermMatches(self, workingSet: ReadOnlyWorkingSet) -> Dict[BindableTerm, Set[Node]]:
        """the total set of terms each variable could possibly match"""

        candidateTermMatches: Dict[BindableTerm, Set[Node]] = defaultdict(set)
        for lhsStmt in self.graph:
            log.debug(f'{INDENT*4} possibles for this lhs stmt: {lhsStmt}')
            for i, trueStmt in enumerate(workingSet):
                # log.debug(f'{INDENT*5} consider this true stmt ({i}): {trueStmt}')

                for v, vals in self._bindingsFromStatement(lhsStmt, trueStmt):
                    candidateTermMatches[v].update(vals)

        return candidateTermMatches

    def _bindingsFromStatement(self, stmt1: Triple, stmt2: Triple) -> Iterator[Tuple[Variable, Set[Node]]]:
        """if these stmts match otherwise, what BNode or Variable mappings do we learn?
        
        e.g. stmt1=(?x B ?y) and stmt2=(A B C), then we yield (?x, {A}) and (?y, {C})
        or   stmt1=(_:x B C) and stmt2=(A B C), then we yield (_:x, {A})
        or   stmt1=(?x B C)  and stmt2=(A B D), then we yield nothing
        """
        bindingsFromStatement = {}
        for term1, term2 in zip(stmt1, stmt2):
            if isinstance(term1, (BNode, Variable)):
                bindingsFromStatement.setdefault(term1, set()).add(term2)
            elif term1 != term2:
                break
        else:
            for v, vals in bindingsFromStatement.items():
                log.debug(f'{INDENT*5} {v=} {vals=}')
                yield v, vals

    def _product(self, candidateTermMatches: Dict[BindableTerm, Set[Node]]) -> Iterator[CandidateBinding]:
        orderedVars, orderedValueSets = _organize(candidateTermMatches)
        self._logCandidates(orderedVars, orderedValueSets)
        log.debug(f'{INDENT*3} trying all permutations:')
        if not orderedValueSets:
            yield CandidateBinding({})
            return

        if not orderedValueSets or not all(orderedValueSets):
            # some var or bnode has no options at all
            return
        rings: List[Iterator[Node]] = [itertools.cycle(valSet) for valSet in orderedValueSets]
        currentSet: List[Node] = [next(ring) for ring in rings]
        starts = [valSet[-1] for valSet in orderedValueSets]
        while True:
            for col, curr in enumerate(currentSet):
                currentSet[col] = next(rings[col])
                log.debug(f'{INDENT*4} currentSet: {repr(currentSet)}')
                yield CandidateBinding(dict(zip(orderedVars, currentSet)))
                if curr is not starts[col]:
                    break
                if col == len(orderedValueSets) - 1:
                    return

    def _logCandidates(self, orderedVars, orderedValueSets):
        if not log.isEnabledFor(logging.DEBUG):
            return
        log.debug(f'{INDENT*3} resulting candidate terms:')
        for v, vals in zip(orderedVars, orderedValueSets):
            log.debug(f'{INDENT*4} {v!r} could be:')
            for val in vals:
                log.debug(f'{INDENT*5}{val!r}')


@dataclass
class BoundLhs:
    lhs: Lhs
    binding: CandidateBinding

    def __post_init__(self):
        self.usedByFuncs = Graph()
        # self._applyFunctions()

    def lhsStmtsWithoutEvals(self):
        for stmt in self.lhs.graph:
            if stmt in self.usedByFuncs:
                continue
            yield stmt

    def _applyFunctions(self):
        """may grow the binding with some results"""
        while True:
            delta = self._applyFunctionsIteration()
            if delta == 0:
                break

    def _applyFunctionsIteration(self):
        before = len(self.binding.binding)
        delta = 0
        for ev in self.lhs.evaluations:
            newBindings, usedGraph = ev.resultBindings(self.binding)
            self.usedByFuncs += usedGraph
            self.binding.addNewBindings(newBindings)
        delta = len(self.binding.binding) - before
        log.debug(f'{INDENT*4} eval rules made {delta} new bindings')
        return delta

    def verify(self, workingSet: ReadOnlyWorkingSet) -> bool:
        """Can this bound lhs be true all at once in workingSet?"""
        rem = cast(Set[Triple], self.lhs.nonStaticRuleStmtsSet.difference(self.usedByFuncs))
        boundLhs = self.binding.apply(rem)

        if log.isEnabledFor(logging.DEBUG):
            boundLhs = list(boundLhs)
            self._logVerifyBanner(boundLhs, workingSet)

        for stmt in boundLhs:
            log.debug(f'{INDENT*4} check for %s', stmt)

            if stmt not in workingSet:
                log.debug(f'{INDENT*5} stmt not known to be true')
                return False
        return True

    def _logVerifyBanner(self, boundLhs, workingSet: ReadOnlyWorkingSet):
        log.debug(f'{INDENT*4}/ verify all bindings against this boundLhs:')
        for stmt in sorted(boundLhs):
            log.debug(f'{INDENT*4}|{INDENT} {stmt}')

        # log.debug(f'{INDENT*4}| and against this workingSet:')
        # for stmt in sorted(workingSet):
        #     log.debug(f'{INDENT*4}|{INDENT} {stmt}')

        log.debug(f'{INDENT*4}\\')


@dataclass
class Rule:
    lhsGraph: Graph
    rhsGraph: Graph
    
    def __post_init__(self):
        self.lhs = Lhs(self.lhsGraph)
        # 
        self.rhsBnodeMap = {}

    def applyRule(self, workingSet: Graph, implied: Graph, stats: Dict):
        for bound in self.lhs.findCandidateBindings(ReadOnlyGraphAggregate([workingSet]), stats):
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


                bound.binding.addNewBindings(CandidateBinding({b: self.rhsBnodeMap[key]}))

            # for lhsBoundStmt in bound.binding.apply(bound.lhsStmtsWithoutEvals()):
            #     log.debug(f'{INDENT*6} adding to workingSet {lhsBoundStmt=}')
            #     workingSet.add(lhsBoundStmt)
            # log.debug(f'{INDENT*6} rhsGraph is good: {list(self.rhsGraph)}')

            for newStmt in bound.binding.apply(self.rhsGraph):
                # log.debug(f'{INDENT*6} adding {newStmt=}')
                workingSet.add(newStmt)
                implied.add(newStmt)


class Inference:

    def __init__(self) -> None:
        self.rules = []

    def setRules(self, g: ConjunctiveGraph):
        self.rules: List[Rule] = []
        for stmt in g:
            if stmt[1] == LOG['implies']:
                self.rules.append(Rule(stmt[0], stmt[2]))
            # other stmts should go to a default working set?

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
        workingSet += graph

        # just the statements that came from RHS's of rules that fired.
        implied = ConjunctiveGraph()

        bailout_iterations = 100
        delta = 1
        stats['initWorkingSet'] = cast(int, workingSet.__len__())
        while delta > 0 and bailout_iterations > 0:
            log.debug('')
            log.info(f'{INDENT*1}*iteration ({bailout_iterations} left)')
            bailout_iterations -= 1
            delta = -len(implied)
            self._iterateAllRules(workingSet, implied, stats)
            delta += len(implied)
            stats['iterations'] += 1
            log.info(f'{INDENT*2} this inference iteration added {delta} more implied stmts')
        stats['timeSpent'] = round(time.time() - startTime, 3)
        stats['impliedStmts'] = len(implied)
        log.info(f'{INDENT*0} Inference done {dict(stats)}. Implied:')
        for st in implied:
            log.info(f'{INDENT*1} {st}')
        return implied

    def _iterateAllRules(self, workingSet: Graph, implied: Graph, stats):
        for i, rule in enumerate(self.rules):
            self._logRuleApplicationHeader(workingSet, i, rule)
            rule.applyRule(workingSet, implied, stats)

    def _logRuleApplicationHeader(self, workingSet, i, r: Rule):
        if not log.isEnabledFor(logging.DEBUG):
            return

        log.debug('')
        log.debug(f'{INDENT*2} workingSet:')
        for j, stmt in enumerate(sorted(workingSet)):
            log.debug(f'{INDENT*3} ({j}) {stmt}')

        log.debug('')
        log.debug(f'{INDENT*2}-applying rule {i}')
        log.debug(f'{INDENT*3} rule def lhs: {graphDump(r.lhsGraph)}')
        log.debug(f'{INDENT*3} rule def rhs: {graphDump(r.rhsGraph)}')


def graphDump(g: Union[Graph, List[Triple]]):
    if not isinstance(g, Graph):
        g2 = Graph()
        g2 += g
        g = g2
    g.bind('', ROOM)
    g.bind('ex', Namespace('http://example.com/'))
    lines = cast(bytes, g.serialize(format='n3')).decode('utf8').splitlines()
    lines = [line.strip() for line in lines if not line.startswith('@prefix')]
    return ' '.join(lines)


def _organize(candidateTermMatches: Dict[BindableTerm, Set[Node]]) -> Tuple[List[BindableTerm], List[List[Node]]]:
    items = list(candidateTermMatches.items())
    items.sort()
    orderedVars: List[BindableTerm] = []
    orderedValueSets: List[List[Node]] = []
    for v, vals in items:
        orderedVars.append(v)
        orderedValues: List[Node] = list(vals)
        orderedValues.sort(key=str)
        orderedValueSets.append(orderedValues)

    return orderedVars, orderedValueSets
