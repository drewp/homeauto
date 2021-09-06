"""
copied from reasoning 2021-08-29. probably same api. should
be able to lib/ this out
"""
import itertools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Set, Tuple, Union, cast

from prometheus_client import Summary
from rdflib import BNode, Graph, Namespace, URIRef
from rdflib.graph import ConjunctiveGraph, ReadOnlyGraphAggregate
from rdflib.term import Node, Variable

from candidate_binding import CandidateBinding
from inference_types import (BindableTerm, EvaluationFailed, ReadOnlyWorkingSet, Triple)
from lhs_evaluation import Evaluation

log = logging.getLogger('infer')
INDENT = '    '

INFER_CALLS = Summary('read_rules_calls', 'calls')

ROOM = Namespace("http://projects.bigasterisk.com/room/")
LOG = Namespace('http://www.w3.org/2000/10/swap/log#')
MATH = Namespace('http://www.w3.org/2000/10/swap/math#')

# Graph() makes a BNode if you don't pass
# identifier, which can be a bottleneck.
GRAPH_ID = URIRef('dont/care')


@dataclass
class Lhs:
    graph: Graph

    staticRuleStmts: Graph = field(default_factory=Graph)
    lhsBindables: Set[BindableTerm] = field(default_factory=set)
    lhsBnodes: Set[BNode] = field(default_factory=set)

    def __post_init__(self):
        for ruleStmt in self.graph:
            varsAndBnodesInStmt = [term for term in ruleStmt if isinstance(term, (Variable, BNode))]
            self.lhsBindables.update(varsAndBnodesInStmt)
            self.lhsBnodes.update(x for x in varsAndBnodesInStmt if isinstance(x, BNode))
            if not varsAndBnodesInStmt:
                self.staticRuleStmts.add(ruleStmt)

        self.evaluations = list(Evaluation.findEvals(self.graph))

    def findCandidateBindings(self, workingSet: ReadOnlyWorkingSet, stats) -> Iterator['BoundLhs']:
        """bindings that fit the LHS of a rule, using statements from workingSet and functions
        from LHS"""
        log.debug(f'{INDENT*3} nodesToBind: {self.lhsBindables}')
        stats['findCandidateBindingsCalls'] += 1

        if not self._allStaticStatementsMatch(workingSet):
            stats['findCandidateBindingEarlyExits'] += 1
            return

        for binding in self._possibleBindings(workingSet, stats):
            log.debug('')
            log.debug(f'{INDENT*4}*trying {binding.binding}')

            if not binding.verify(workingSet):
                log.debug(f'{INDENT*4} this binding did not verify')
                stats['permCountFailingVerify'] += 1
                continue

            stats['permCountSucceeding'] += 1
            yield binding

    def _possibleBindings(self, workingSet, stats) -> Iterator['BoundLhs']:
        """this yields at least the working bindings, and possibly others"""
        candidateTermMatches: Dict[BindableTerm, Set[Node]] = self._allCandidateTermMatches(workingSet)

        orderedVars, orderedValueSets = _organize(candidateTermMatches)
        self._logCandidates(orderedVars, orderedValueSets)

        log.debug(f'{INDENT*3} trying all permutations:')
        for perm in itertools.product(*orderedValueSets):
            try:
                yield BoundLhs(self, CandidateBinding(dict(zip(orderedVars, perm))))
            except EvaluationFailed:
                stats['permCountFailingEval'] += 1

    def _allStaticStatementsMatch(self, workingSet: ReadOnlyWorkingSet) -> bool:
        for ruleStmt in self.staticRuleStmts:
            if ruleStmt not in workingSet:
                log.debug(f'{INDENT*3} {ruleStmt} not in working set- skip rule')
                return False
        return True

    def _allCandidateTermMatches(self, workingSet: ReadOnlyWorkingSet) -> Dict[BindableTerm, Set[Node]]:
        """the total set of terms each variable could possibly match"""

        candidateTermMatches: Dict[BindableTerm, Set[Node]] = defaultdict(set)
        for lhsStmt in self.graph:
            log.debug(f'{INDENT*4} possibles for this lhs stmt: {lhsStmt}')
            for i, trueStmt in enumerate(sorted(workingSet)):
                # log.debug(f'{INDENT*5} consider this true stmt ({i}): {trueStmt}')

                for v, vals in self._bindingsFromStatement(lhsStmt, trueStmt):
                    candidateTermMatches[v].update(vals)

        for trueStmt in itertools.chain(workingSet, self.graph):
            for b in self.lhsBnodes:
                for t in [trueStmt[0], trueStmt[2]]:
                    if isinstance(t, (URIRef, BNode)):
                        candidateTermMatches[b].add(t)
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
        self.usedByFuncs = Graph(identifier=GRAPH_ID)
        self.graphWithoutEvals = self._graphWithoutEvals()

    def _graphWithoutEvals(self) -> Graph:
        g = Graph(identifier=GRAPH_ID)
        self._applyFunctions()

        for stmt in self.lhs.graph:
            if stmt not in self.usedByFuncs:
                g.add(stmt)
        return g

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
            log.debug(f'{INDENT*3} found Evaluation')

            newBindings, usedGraph = ev.resultBindings(self.binding)
            self.usedByFuncs += usedGraph
            self.binding.addNewBindings(newBindings)
            delta = len(self.binding.binding) - before
            if log.isEnabledFor(logging.DEBUG):
                dump = "(...)"
                if cast(int, usedGraph.__len__()) < 20:
                    dump = graphDump(usedGraph)
                log.debug(f'{INDENT*4} rule {dump} made {delta} new bindings')
        return delta


    def verify(self, workingSet: ReadOnlyWorkingSet) -> bool:
        """Can this bound lhs be true all at once in workingSet?"""
        boundLhs = list(self.binding.apply(self.lhs.graph))
        boundUsedByFuncs = list(self.binding.apply(self.usedByFuncs))

        self._logVerifyBanner(boundLhs, workingSet, boundUsedByFuncs)

        for stmt in boundLhs:
            log.debug(f'{INDENT*4} check for {stmt}')

            if stmt in boundUsedByFuncs:
                pass
            elif stmt in workingSet:
                pass
            else:
                log.debug(f'{INDENT*5} stmt not known to be true')
                return False
        return True

    def _logVerifyBanner(self, boundLhs, workingSet: ReadOnlyWorkingSet, boundUsedByFuncs):
        if not log.isEnabledFor(logging.DEBUG):
            return
        log.debug(f'{INDENT*4}/ verify all bindings against this boundLhs:')
        for stmt in sorted(boundLhs):
            log.debug(f'{INDENT*4}|{INDENT} {stmt}')

        # log.debug(f'{INDENT*4}| and against this workingSet:')
        # for stmt in sorted(workingSet):
        #     log.debug(f'{INDENT*4}|{INDENT} {stmt}')

        stmts = sorted(boundUsedByFuncs)
        if stmts:
            log.debug(f'{INDENT*4}| while ignoring these usedByFuncs:')
            for stmt in stmts:
                log.debug(f'{INDENT*4}|{INDENT} {stmt}')
        log.debug(f'{INDENT*4}\\')


@dataclass
class Rule:
    lhsGraph: Graph
    rhsGraph: Graph

    def __post_init__(self):
        self.lhs = Lhs(self.lhsGraph)


class Inference:

    def __init__(self) -> None:
        self.rules = []

    def setRules(self, g: ConjunctiveGraph):
        self.rules: List[Rule] = []
        for stmt in g:
            if stmt[1] == LOG['implies']:
                self.rules.append(Rule(stmt[0], stmt[2]))
            # others should go to a default working set?

    @INFER_CALLS.time()
    def infer(self, graph: Graph):
        """
        returns new graph of inferred statements.
        """
        log.info(f'{INDENT*0} Begin inference of graph len={graph.__len__()} with rules len={len(self.rules)}:')
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
        for i, r in enumerate(self.rules):
            self._logRuleApplicationHeader(workingSet, i, r)
            _applyRule(r.lhs, r.rhsGraph, workingSet, implied, stats)

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


def _applyRule(lhs: Lhs, rhs: Graph, workingSet: Graph, implied: Graph, stats: Dict):
    for bound in lhs.findCandidateBindings(ReadOnlyGraphAggregate([workingSet]), stats):
        log.debug(f'{INDENT*3} rule has a working binding:')

        for lhsBoundStmt in bound.binding.apply(bound.graphWithoutEvals):
            log.debug(f'{INDENT*5} adding {lhsBoundStmt=}')
            workingSet.add(lhsBoundStmt)
        for newStmt in bound.binding.apply(rhs):
            log.debug(f'{INDENT*5} adding {newStmt=}')
            workingSet.add(newStmt)
            implied.add(newStmt)


def graphDump(g: Union[Graph, List[Triple]]):
    if not isinstance(g, Graph):
        log.warning(f"it's a {type(g)}")
        g2 = Graph()
        g2 += g
        g = g2
    g.bind('', ROOM)
    g.bind('ex', Namespace('http://example.com/'))
    lines = cast(bytes, g.serialize(format='n3')).decode('utf8').splitlines()
    lines = [line for line in lines if not line.startswith('@prefix')]
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
