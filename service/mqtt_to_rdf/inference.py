"""
copied from reasoning 2021-08-29. probably same api. should
be able to lib/ this out
"""
import itertools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Iterable, Iterator, List, Set, Tuple, Union, cast

from prometheus_client import Summary
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.graph import ConjunctiveGraph, ReadOnlyGraphAggregate
from rdflib.term import Node, Variable

from lhs_evaluation import EvaluationFailed, Evaluation

log = logging.getLogger('infer')
INDENT = '    '

Triple = Tuple[Node, Node, Node]
Rule = Tuple[Graph, Node, Graph]
BindableTerm = Union[Variable, BNode]
ReadOnlyWorkingSet = ReadOnlyGraphAggregate

INFER_CALLS = Summary('read_rules_calls', 'calls')

ROOM = Namespace("http://projects.bigasterisk.com/room/")
LOG = Namespace('http://www.w3.org/2000/10/swap/log#')
MATH = Namespace('http://www.w3.org/2000/10/swap/math#')

# Graph() makes a BNode if you don't pass
# identifier, which can be a bottleneck.
GRAPH_ID = URIRef('dont/care')


class BindingUnknown(ValueError):
    """e.g. we were asked to make the bound version 
    of (A B ?c) and we don't have a binding for ?c
    """


@dataclass
class CandidateBinding:
    binding: Dict[BindableTerm, Node]

    def __repr__(self):
        b = " ".join("%s=%s" % (k, v) for k, v in sorted(self.binding.items()))
        return f'CandidateBinding({b})'

    def apply(self, g: Graph) -> Iterator[Triple]:
        for stmt in g:
            try:
                bound = (self._applyTerm(stmt[0]), self._applyTerm(stmt[1]), self._applyTerm(stmt[2]))
            except BindingUnknown:
                continue
            yield bound

    def _applyTerm(self, term: Node):
        if isinstance(term, (Variable, BNode)):
            if term in self.binding:
                return self.binding[term]
            else:
                raise BindingUnknown()
        return term

    def applyFunctions(self, lhs) -> Graph:
        """may grow the binding with some results"""
        usedByFuncs = Graph(identifier=GRAPH_ID)
        while True:
            delta = self._applyFunctionsIteration(lhs, usedByFuncs)
            if delta == 0:
                break
        return usedByFuncs

    def _applyFunctionsIteration(self, lhs, usedByFuncs: Graph):
        before = len(self.binding)
        delta = 0
        for ev in lhs.evaluations:
            log.debug(f'{INDENT*3} found Evaluation')

            newBindings, usedGraph = ev.resultBindings(self.binding)
            usedByFuncs += usedGraph
            self._addNewBindings(newBindings)
            delta = len(self.binding) - before
            if log.isEnabledFor(logging.DEBUG):
                dump = "(...)"
                if cast(int, usedGraph.__len__()) < 20:
                    dump = graphDump(usedGraph)
                log.debug(f'{INDENT*4} rule {dump} made {delta} new bindings')
        return delta

    def _addNewBindings(self, newBindings):
        for k, v in newBindings.items():
            if k in self.binding and self.binding[k] != v:
                raise ValueError(f'conflict- thought {k} would be {self.binding[k]} but another Evaluation said it should be {v}')
            self.binding[k] = v

    def verify(self, lhs: 'Lhs', workingSet: ReadOnlyWorkingSet, usedByFuncs: Graph) -> bool:
        """Can this lhs be true all at once in workingSet? Does it match with these bindings?"""
        boundLhs = list(self.apply(lhs.graph))
        boundUsedByFuncs = list(self.apply(usedByFuncs))

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
class Lhs:
    graph: Graph
    stats: Dict

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

    def findCandidateBindings(self, workingSet: ReadOnlyWorkingSet) -> Iterator[CandidateBinding]:
        """bindings that fit the LHS of a rule, using statements from workingSet and functions
        from LHS"""
        log.debug(f'{INDENT*3} nodesToBind: {self.lhsBindables}')
        self.stats['findCandidateBindingsCalls'] += 1

        if not self._allStaticStatementsMatch(workingSet):
            self.stats['findCandidateBindingEarlyExits'] += 1
            return

        candidateTermMatches: Dict[BindableTerm, Set[Node]] = self._allCandidateTermMatches(workingSet)

        orderedVars, orderedValueSets = _organize(candidateTermMatches)

        self._logCandidates(orderedVars, orderedValueSets)

        log.debug(f'{INDENT*3} trying all permutations:')

        for perm in itertools.product(*orderedValueSets):
            binding = CandidateBinding(dict(zip(orderedVars, perm)))
            log.debug('')
            log.debug(f'{INDENT*4}*trying {binding}')

            try:
                usedByFuncs = binding.applyFunctions(self)
            except EvaluationFailed:
                self.stats['permCountFailingEval'] += 1
                continue

            if not binding.verify(self, workingSet, usedByFuncs):
                log.debug(f'{INDENT*4} this binding did not verify')
                self.stats['permCountFailingVerify'] += 1
                continue

            self.stats['permCountSucceeding'] += 1
            yield binding

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

    def graphWithoutEvals(self, binding: CandidateBinding) -> Graph:
        g = Graph(identifier=GRAPH_ID)
        usedByFuncs = binding.applyFunctions(self)

        for stmt in self.graph:
            if stmt not in usedByFuncs:
                g.add(stmt)
        return g

    def _logCandidates(self, orderedVars, orderedValueSets):
        if not log.isEnabledFor(logging.DEBUG):
            return
        log.debug(f'{INDENT*3} resulting candidate terms:')
        for v, vals in zip(orderedVars, orderedValueSets):
            log.debug(f'{INDENT*4} {v!r} could be:')
            for val in vals:
                log.debug(f'{INDENT*5}{val!r}')


class Inference:

    def __init__(self) -> None:
        self.rules = ConjunctiveGraph()

    def setRules(self, g: ConjunctiveGraph):
        self.rules = ConjunctiveGraph()
        for stmt in g:
            if stmt[1] == LOG['implies']:
                self.rules.add(stmt)
            # others should go to a default working set?

    @INFER_CALLS.time()
    def infer(self, graph: Graph):
        """
        returns new graph of inferred statements.
        """
        log.info(f'{INDENT*0} Begin inference of graph len={graph.__len__()} with rules len={len(self.rules)}:')
        startTime = time.time()
        self.stats: Dict[str, Union[int, float]] = defaultdict(lambda: 0)
        # everything that is true: the input graph, plus every rule conclusion we can make
        workingSet = Graph()
        workingSet += graph

        # just the statements that came from RHS's of rules that fired.
        implied = ConjunctiveGraph()

        bailout_iterations = 100
        delta = 1
        self.stats['initWorkingSet'] = cast(int, workingSet.__len__())
        while delta > 0 and bailout_iterations > 0:
            log.info(f'{INDENT*1}*iteration ({bailout_iterations} left)')
            bailout_iterations -= 1
            delta = -len(implied)
            self._iterateAllRules(workingSet, implied)
            delta += len(implied)
            self.stats['iterations'] += 1
            log.info(f'{INDENT*2} this inference iteration added {delta} more implied stmts')
        self.stats['timeSpent'] = round(time.time() - startTime, 3)
        self.stats['impliedStmts'] = len(implied)
        log.info(f'{INDENT*0} Inference done {dict(self.stats)}. Implied:')
        for st in implied:
            log.info(f'{INDENT*1} {st}')
        return implied

    def _iterateAllRules(self, workingSet: Graph, implied: Graph):
        for i, r in enumerate(self.rules):
            self._logRuleApplicationHeader(workingSet, i, r)
            _applyRule(Lhs(r[0], self.stats), r[2], workingSet, implied, self.stats)

    def _logRuleApplicationHeader(self, workingSet, i, r):
        if not log.isEnabledFor(logging.DEBUG):
            return

        log.debug('')
        log.debug(f'{INDENT*2} workingSet:')
        for j, stmt in enumerate(sorted(workingSet)):
            log.debug(f'{INDENT*3} ({j}) {stmt}')

        log.debug('')
        log.debug(f'{INDENT*2}-applying rule {i}')
        log.debug(f'{INDENT*3} rule def lhs: {graphDump(r[0])}')
        log.debug(f'{INDENT*3} rule def rhs: {graphDump(r[2])}')


def _applyRule(lhs: Lhs, rhs: Graph, workingSet: Graph, implied: Graph, stats: Dict):
    for binding in lhs.findCandidateBindings(ReadOnlyGraphAggregate([workingSet])):
        log.debug(f'{INDENT*3} rule has a working binding:')

        for lhsBoundStmt in binding.apply(lhs.graphWithoutEvals(binding)):
            log.debug(f'{INDENT*5} adding {lhsBoundStmt=}')
            workingSet.add(lhsBoundStmt)
        for newStmt in binding.apply(rhs):
            log.debug(f'{INDENT*5} adding {newStmt=}')
            workingSet.add(newStmt)
            implied.add(newStmt)


def graphDump(g: Union[Graph, List[Triple]]):
    if not isinstance(g, Graph):
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
