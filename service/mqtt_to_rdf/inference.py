"""
copied from reasoning 2021-08-29. probably same api. should
be able to lib/ this out
"""
import itertools
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Iterable, Iterator, List, Set, Tuple, Union, cast

from prometheus_client import Summary
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.graph import ConjunctiveGraph, ReadOnlyGraphAggregate
from rdflib.term import Node, Variable

log = logging.getLogger('infer')
INDENT = '    '

Triple = Tuple[Node, Node, Node]
Rule = Tuple[Graph, Node, Graph]
BindableTerm = Union[Variable, BNode]
ReadOnlyWorkingSet = ReadOnlyGraphAggregate

READ_RULES_CALLS = Summary('read_rules_calls', 'calls')

ROOM = Namespace("http://projects.bigasterisk.com/room/")
LOG = Namespace('http://www.w3.org/2000/10/swap/log#')
MATH = Namespace('http://www.w3.org/2000/10/swap/math#')


class EvaluationFailed(ValueError):
    """e.g. we were given (5 math:greaterThan 6)"""


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
        usedByFuncs = Graph()
        while True:
            delta = self._applyFunctionsIteration(lhs, usedByFuncs)
            if delta == 0:
                break
        return usedByFuncs

    def _applyFunctionsIteration(self, lhs, usedByFuncs: Graph):
        before = len(self.binding)
        delta = 0
        for ev in Evaluation.findEvals(lhs.graph):
            log.debug(f'{INDENT*3} found Evaluation')

            newBindings, usedGraph = ev.resultBindings(self.binding)
            usedByFuncs += usedGraph
            self._addNewBindings(newBindings)
            delta = len(self.binding) - before
            dump = "(...)"
            if log.isEnabledFor(logging.DEBUG) and cast(int, usedGraph.__len__()) < 20:
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

        self.logVerifyBanner(boundLhs, workingSet, boundUsedByFuncs)

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

    def logVerifyBanner(self, boundLhs, workingSet: ReadOnlyWorkingSet, boundUsedByFuncs):
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

    def findCandidateBindings(self, workingSet: ReadOnlyWorkingSet) -> Iterator[CandidateBinding]:
        """bindings that fit the LHS of a rule, using statements from workingSet and functions
        from LHS"""
        log.debug(f'{INDENT*3} nodesToBind: {self.lhsBindables}')

        if not self.allStaticStatementsMatch(workingSet):
            return

        candidateTermMatches: Dict[BindableTerm, Set[Node]] = self.allCandidateTermMatches(workingSet)

        orderedVars, orderedValueSets = organize(candidateTermMatches)

        self.logCandidates(orderedVars, orderedValueSets)

        log.debug(f'{INDENT*3} trying all permutations:')

        for perm in itertools.product(*orderedValueSets):
            binding = CandidateBinding(dict(zip(orderedVars, perm)))
            log.debug('')
            log.debug(f'{INDENT*4}*trying {binding}')

            try:
                usedByFuncs = binding.applyFunctions(self)
            except EvaluationFailed:
                continue

            if not binding.verify(self, workingSet, usedByFuncs):
                log.debug(f'{INDENT*4} this binding did not verify')
                continue
            yield binding

    def allStaticStatementsMatch(self, workingSet: ReadOnlyWorkingSet) -> bool:
        for ruleStmt in self.staticRuleStmts:
            if ruleStmt not in workingSet:
                log.debug(f'{INDENT*3} {ruleStmt} not in working set- skip rule')
                return False
        return True

    def allCandidateTermMatches(self, workingSet: ReadOnlyWorkingSet) -> Dict[BindableTerm, Set[Node]]:
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
        g = Graph()
        usedByFuncs = binding.applyFunctions(self)

        for stmt in self.graph:
            if stmt not in usedByFuncs:
                g.add(stmt)
        return g

    def logCandidates(self, orderedVars, orderedValueSets):
        if not log.isEnabledFor(logging.DEBUG):
            return
        log.debug(f'{INDENT*3} resulting candidate terms:')
        for v, vals in zip(orderedVars, orderedValueSets):
            log.debug(f'{INDENT*4} {v!r} could be:')
            for val in vals:
                log.debug(f'{INDENT*5}{val!r}')


class Evaluation:
    """some lhs statements need to be evaluated with a special function 
    (e.g. math) and then not considered for the rest of the rule-firing 
    process. It's like they already 'matched' something, so they don't need
    to match a statement from the known-true working set.
    
    One Evaluation instance is for one function call.
    """

    @staticmethod
    def findEvals(graph: Graph) -> Iterator['Evaluation']:
        for stmt in graph.triples((None, MATH['sum'], None)):
            operands, operandsStmts = parseList(graph, stmt[0])
            yield Evaluation(operands, stmt, operandsStmts)

        for stmt in graph.triples((None, MATH['greaterThan'], None)):
            yield Evaluation([stmt[0], stmt[2]], stmt, [])

        for stmt in graph.triples((None, ROOM['asFarenheit'], None)):
            yield Evaluation([stmt[0]], stmt, [])

    # internal, use findEvals
    def __init__(self, operands: List[Node], mainStmt: Triple, otherStmts: Iterable[Triple]) -> None:
        self.operands = operands
        self.operandsStmts = Graph()
        self.operandsStmts += otherStmts  # may grow
        self.operandsStmts.add(mainStmt)
        self.stmt = mainStmt

    def resultBindings(self, inputBindings) -> Tuple[Dict[BindableTerm, Node], Graph]:
        """under the bindings so far, what would this evaluation tell us, and which stmts would be consumed from doing so?"""
        pred = self.stmt[1]
        objVar: Node = self.stmt[2]
        boundOperands = []
        for op in self.operands:
            if isinstance(op, Variable):
                try:
                    op = inputBindings[op]
                except KeyError:
                    return {}, self.operandsStmts

            boundOperands.append(op)

        if pred == MATH['sum']:
            obj = Literal(sum(map(numericNode, boundOperands)))
            if not isinstance(objVar, Variable):
                raise TypeError(f'expected Variable, got {objVar!r}')
            res: Dict[BindableTerm, Node] = {objVar: obj}
        elif pred == ROOM['asFarenheit']:
            if len(boundOperands) != 1:
                raise ValueError(":asFarenheit takes 1 subject operand")
            f = Literal(Decimal(numericNode(boundOperands[0])) * 9 / 5 + 32)
            if not isinstance(objVar, Variable):
                raise TypeError(f'expected Variable, got {objVar!r}')
            res: Dict[BindableTerm, Node] = {objVar: f}
        elif pred == MATH['greaterThan']:
            if not (numericNode(boundOperands[0]) > numericNode(boundOperands[1])):
                raise EvaluationFailed()
            res: Dict[BindableTerm, Node] = {}
        else:
            raise NotImplementedError(repr(pred))

        return res, self.operandsStmts


def numericNode(n: Node):
    if not isinstance(n, Literal):
        raise TypeError(f'expected Literal, got {n=}')
    val = n.toPython()
    if not isinstance(val, (int, float, Decimal)):
        raise TypeError(f'expected number, got {val=}')
    return val


class Inference:

    def __init__(self) -> None:
        self.rules = ConjunctiveGraph()

    def setRules(self, g: ConjunctiveGraph):
        self.rules = ConjunctiveGraph()
        for stmt in g:
            if stmt[1] == LOG['implies']:
                self.rules.add(stmt)
            # others should go to a default working set?

    def infer(self, graph: Graph):
        """
        returns new graph of inferred statements.
        """
        log.info(f'{INDENT*0} Begin inference of graph len={graph.__len__()} with rules len={len(self.rules)}:')

        # everything that is true: the input graph, plus every rule conclusion we can make
        workingSet = Graph()
        workingSet += graph

        # just the statements that came from RHS's of rules that fired.
        implied = ConjunctiveGraph()

        bailout_iterations = 100
        delta = 1
        while delta > 0 and bailout_iterations > 0:
            log.info(f'{INDENT*1}*iteration ({bailout_iterations} left)')
            bailout_iterations -= 1
            delta = -len(implied)
            self._iterateAllRules(workingSet, implied)
            delta += len(implied)
            log.info(f'{INDENT*2} this inference iteration added {delta} more implied stmts')
        log.info(f'{INDENT*0} Inference done; {len(implied)} stmts implied:')
        for st in implied:
            log.info(f'{INDENT*1} {st}')
        return implied

    def _iterateAllRules(self, workingSet: Graph, implied: Graph):
        for i, r in enumerate(self.rules):
            self.logRuleApplicationHeader(workingSet, i, r)
            applyRule(Lhs(r[0]), r[2], workingSet, implied)

    def logRuleApplicationHeader(self, workingSet, i, r):
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


def applyRule(lhs: Lhs, rhs: Graph, workingSet: Graph, implied: Graph):
    for binding in lhs.findCandidateBindings(ReadOnlyGraphAggregate([workingSet])):
        log.debug(f'{INDENT*3} rule has a working binding:')

        for lhsBoundStmt in binding.apply(lhs.graphWithoutEvals(binding)):
            log.debug(f'{INDENT*5} adding {lhsBoundStmt=}')
            workingSet.add(lhsBoundStmt)
        for newStmt in binding.apply(rhs):
            log.debug(f'{INDENT*5} adding {newStmt=}')
            workingSet.add(newStmt)
            implied.add(newStmt)


def parseList(graph, subj) -> Tuple[List[Node], Set[Triple]]:
    """"Do like Collection(g, subj) but also return all the 
    triples that are involved in the list"""
    out = []
    used = set()
    cur = subj
    while cur != RDF.nil:
        out.append(graph.value(cur, RDF.first))
        used.add((cur, RDF.first, out[-1]))

        next = graph.value(cur, RDF.rest)
        used.add((cur, RDF.rest, next))

        cur = next
    return out, used


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


def organize(candidateTermMatches: Dict[BindableTerm, Set[Node]]) -> Tuple[List[BindableTerm], List[List[Node]]]:
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
