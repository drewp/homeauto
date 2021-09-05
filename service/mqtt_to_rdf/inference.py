"""
copied from reasoning 2021-08-29. probably same api. should
be able to lib/ this out
"""
from collections import defaultdict
import itertools
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterator, List, Set, Tuple, Union, cast
from urllib.request import OpenerDirector

from prometheus_client import Summary
from rdflib import BNode, Graph, Literal, Namespace, URIRef, RDF
from rdflib.collection import Collection
from rdflib.graph import ConjunctiveGraph, ReadOnlyGraphAggregate
from rdflib.term import Node, Variable

log = logging.getLogger('infer')
INDENT = '    '

Triple = Tuple[Node, Node, Node]
Rule = Tuple[Graph, Node, Graph]
BindableTerm = Union[Variable, BNode]

READ_RULES_CALLS = Summary('read_rules_calls', 'calls')

ROOM = Namespace("http://projects.bigasterisk.com/room/")
LOG = Namespace('http://www.w3.org/2000/10/swap/log#')
MATH = Namespace('http://www.w3.org/2000/10/swap/math#')


@dataclass
class _RuleMatch:
    """one way that a rule can match the working set"""
    vars: Dict[Variable, Node]


ReadOnlyWorkingSet = ReadOnlyGraphAggregate

filterFuncs = {
    MATH['greaterThan'],
}


class CandidateBinding:

    def __init__(self, binding: Dict[BindableTerm, Node]):
        self.binding = binding  # mutable!

    def __repr__(self):
        b = " ".join("%s=%s" % (k, v) for k, v in sorted(self.binding.items()))
        return f'CandidateBinding({b})'

    def apply(self, g: Graph) -> Iterator[Triple]:
        for stmt in g:
            stmt = list(stmt)
            for i, term in enumerate(stmt):
                if isinstance(term, (Variable, BNode)):
                    if term in self.binding:
                        stmt[i] = self.binding[term]
            else:
                yield cast(Triple, stmt)

    def applyFunctions(self, lhs):
        """may grow the binding with some results"""
        usedByFuncs = Graph()
        while True:
            before = len(self.binding)
            delta = 0
            for ev in Evaluation.findEvals(lhs):
                log.debug(f'{INDENT*3} found Evaluation')

                newBindings, usedGraph = ev.resultBindings(self.binding)
                usedByFuncs += usedGraph
                for k, v in newBindings.items():
                    if k in self.binding and self.binding[k] != v:
                        raise ValueError(
                            f'conflict- thought {k} would be {self.binding[k]} but another Evaluation said it should be {v}')
                    self.binding[k] = v
                delta = len(self.binding) - before
                log.debug(f'{INDENT*4} rule {graphDump(usedGraph)} made {delta} new bindings')
            if delta == 0:
                break
        return usedByFuncs

    def verify(self, lhs: 'Lhs', workingSet: ReadOnlyWorkingSet, usedByFuncs: Graph) -> bool:
        """Can this lhs be true all at once in workingSet? Does it match with these bindings?"""
        boundLhs = list(self.apply(lhs._g))
        boundUsedByFuncs = list(self.apply(usedByFuncs))

        self.logVerifyBanner(boundLhs, workingSet, boundUsedByFuncs)

        for stmt in boundLhs:
            log.debug(f'{INDENT*4} check for {stmt}')

            if stmt[1] in filterFuncs:
                if not mathTest(*stmt):
                    log.debug(f'{INDENT*5} binding was invalid because {stmt}) is not true')
                    return False
            elif stmt in boundUsedByFuncs:
                pass
            elif stmt in workingSet:
                pass
            else:
                log.debug(f'{INDENT*5} binding was invalid because {stmt}) is not known to be true')
                return False
        log.debug(f"{INDENT*5} this rule's lhs can work under this binding")
        return True

    def logVerifyBanner(self, boundLhs, workingSet: ReadOnlyWorkingSet, boundUsedByFuncs):
        if not log.isEnabledFor(logging.DEBUG):
            return
        log.debug(f'{INDENT*4}/ verify all bindings against this lhs:')
        for stmt in sorted(boundLhs):
            log.debug(f'{INDENT*4}|{INDENT} {stmt}')

        log.debug(f'{INDENT*4}| and against this workingSet:')
        for stmt in sorted(workingSet):
            log.debug(f'{INDENT*4}|{INDENT} {stmt}')

        log.debug(f'{INDENT*4}| while ignoring these usedByFuncs:')
        for stmt in sorted(boundUsedByFuncs):
            log.debug(f'{INDENT*4}|{INDENT} {stmt}')
        log.debug(f'{INDENT*4}\\')


class Lhs:

    def __init__(self, existingGraph):
        self._g = existingGraph

    def findCandidateBindings(self, workingSet: ReadOnlyWorkingSet) -> Iterator[CandidateBinding]:
        """bindings that fit the LHS of a rule, using statements from workingSet and functions
        from LHS"""
        nodesToBind = self.nodesToBind()
        log.debug(f'{INDENT*2} nodesToBind: {nodesToBind}')

        if not self.allStaticStatementsMatch(workingSet):
            return

        candidateTermMatches: Dict[BindableTerm, Set[Node]] = self.allCandidateTermMatches(workingSet)

        # for n in nodesToBind:
        #     if n not in candidateTermMatches:
        #         candidateTermMatches[n] = set()

        orderedVars, orderedValueSets = organize(candidateTermMatches)

        self.logCandidates(orderedVars, orderedValueSets)

        log.debug(f'{INDENT*2} trying all permutations:')

        for perm in itertools.product(*orderedValueSets):
            binding = CandidateBinding(dict(zip(orderedVars, perm)))
            log.debug('')
            log.debug(f'{INDENT*3}*trying {binding}')

            usedByFuncs = binding.applyFunctions(self)

            if not binding.verify(self, workingSet, usedByFuncs):
                log.debug(f'{INDENT*3} this binding did not verify')
                continue
            yield binding

    def nodesToBind(self) -> List[BindableTerm]:
        nodes: Set[BindableTerm] = set()
        staticRuleStmts = Graph()
        for ruleStmt in self._g:
            varsInStmt = [v for v in ruleStmt if isinstance(v, (Variable, BNode))]
            nodes.update(varsInStmt)
            if (not varsInStmt  # ok
                    #and not any(isinstance(t, BNode) for t in ruleStmt)  # approx
               ):
                staticRuleStmts.add(ruleStmt)
        return sorted(nodes)

    def allStaticStatementsMatch(self, workingSet: ReadOnlyWorkingSet) -> bool:
        staticRuleStmts = Graph()
        for ruleStmt in self._g:
            varsInStmt = [v for v in ruleStmt if isinstance(v, (Variable, BNode))]
            if (not varsInStmt  # ok
                    #and not any(isinstance(t, BNode) for t in ruleStmt)  # approx
               ):
                staticRuleStmts.add(ruleStmt)

        for ruleStmt in staticRuleStmts:
            if ruleStmt not in workingSet:
                log.debug(f'{INDENT*3} {ruleStmt} not in working set- skip rule')
                return False
        return True

    def allCandidateTermMatches(self, workingSet: ReadOnlyWorkingSet) -> Dict[BindableTerm, Set[Node]]:
        """the total set of terms each variable could possibly match"""

        candidateTermMatches: Dict[BindableTerm, Set[Node]] = defaultdict(set)
        lhsBnodes: Set[BNode] = set()
        for lhsStmt in self._g:
            log.debug(f'{INDENT*3} possibles for this lhs stmt: {lhsStmt}')
            for i, trueStmt in enumerate(sorted(workingSet)):
                log.debug(f'{INDENT*4} consider this true stmt ({i}): {trueStmt}')
                bindingsFromStatement: Dict[Variable, Set[Node]] = {}
                for lhsTerm, trueTerm in zip(lhsStmt, trueStmt):
                    if isinstance(lhsTerm, BNode):
                        lhsBnodes.add(lhsTerm)
                    elif isinstance(lhsTerm, Variable):
                        bindingsFromStatement.setdefault(lhsTerm, set()).add(trueTerm)
                    elif lhsTerm != trueTerm:
                        break
                else:
                    for v, vals in bindingsFromStatement.items():
                        candidateTermMatches[v].update(vals)

        for trueStmt in itertools.chain(workingSet, self._g):
            for b in lhsBnodes:
                for t in [trueStmt[0], trueStmt[2]]:
                    if isinstance(t, (URIRef, BNode)):
                        candidateTermMatches[b].add(t)
        return candidateTermMatches

    def graphWithoutEvals(self, binding: CandidateBinding) -> Graph:
        g = Graph()
        usedByFuncs = binding.applyFunctions(self)

        for stmt in self._g:
            if stmt not in usedByFuncs:
                g.add(stmt)
        return g

    def logCandidates(self, orderedVars, orderedValueSets):
        if not log.isEnabledFor(logging.DEBUG):
            return
        log.debug(f'{INDENT*2} resulting candidate terms:')
        for v, vals in zip(orderedVars, orderedValueSets):
            log.debug(f'{INDENT*3} {v} could be:')
            for val in vals:
                log.debug(f'{INDENT*4}{val}')


class Evaluation:
    """some lhs statements need to be evaluated with a special function 
    (e.g. math) and then not considered for the rest of the rule-firing 
    process. It's like they already 'matched' something, so they don't need
    to match a statement from the known-true working set."""

    @staticmethod
    def findEvals(lhs: Lhs) -> Iterator['Evaluation']:
        for stmt in lhs._g.triples((None, MATH['sum'], None)):
            # shouldn't be redoing this here
            operands, operandsStmts = parseList(lhs._g, stmt[0])
            g = Graph()
            g += operandsStmts
            yield Evaluation(operands, g, stmt)

        for stmt in lhs._g.triples((None, ROOM['asFarenheit'], None)):
            g = Graph()
            g.add(stmt)
            yield Evaluation([stmt[0]], g, stmt)

    # internal, use findEvals
    def __init__(self, operands: List[Node], operandsStmts: Graph, stmt: Triple) -> None:
        self.operands = operands
        self.operandsStmts = operandsStmts
        self.stmt = stmt

    def resultBindings(self, inputBindings) -> Tuple[Dict[BindableTerm, Node], Graph]:
        """under the bindings so far, what would this evaluation tell us, and which stmts would be consumed from doing so?"""
        pred = self.stmt[1]
        objVar = self.stmt[2]
        boundOperands = []
        for o in self.operands:
            if isinstance(o, Variable):
                try:
                    o = inputBindings[o]
                except KeyError:
                    return {}, self.operandsStmts

            boundOperands.append(o)

        if not isinstance(objVar, Variable):
            raise TypeError(f'expected Variable, got {objVar!r}')

        if pred == MATH['sum']:
            log.debug(f'{INDENT*4} sum {list(map(self.numericNode, boundOperands))}')
            obj = cast(Literal, Literal(sum(map(self.numericNode, boundOperands))))
            self.operandsStmts.add(self.stmt)
            return {objVar: obj}, self.operandsStmts
        elif pred == ROOM['asFarenheit']:
            if len(boundOperands) != 1:
                raise ValueError(":asFarenheit takes 1 subject operand")
            f = Literal(Decimal(self.numericNode(boundOperands[0])) * 9 / 5 + 32)
            g = Graph()
            g.add(self.stmt)

            log.debug('made 1 st graph')
            return {objVar: f}, g
        else:
            raise NotImplementedError()

    def numericNode(self, n: Node):
        if not isinstance(n, Literal):
            raise TypeError(f'expected Literal, got {n=}')
        val = n.toPython()
        if not isinstance(val, (int, float, Decimal)):
            raise TypeError(f'expected number, got {val=}')
        return val


# merge into evaluation, raising a Invalid for impossible stmts
def mathTest(subj, pred, obj):
    x = subj.toPython()
    y = obj.toPython()
    if pred == MATH['greaterThan']:
        return x > y
    else:
        raise NotImplementedError(pred)


class Inference:

    def __init__(self) -> None:
        self.rules = ConjunctiveGraph()

    def setRules(self, g: ConjunctiveGraph):
        self.rules = g

    def infer(self, graph: Graph):
        """
        returns new graph of inferred statements.
        """
        log.debug(f'{INDENT*0} Begin inference of graph len={graph.__len__()} with rules len={len(self.rules)}:')

        # everything that is true: the input graph, plus every rule conclusion we can make
        workingSet = Graph()
        workingSet += graph

        # just the statements that came from rule RHS's.
        implied = ConjunctiveGraph()

        bailout_iterations = 100
        delta = 1
        while delta > 0 and bailout_iterations > 0:
            log.debug(f'{INDENT*1}*iteration ({bailout_iterations} left)')
            bailout_iterations -= 1
            delta = -len(implied)
            self._iterateAllRules(workingSet, implied)
            delta += len(implied)
            log.info(f'{INDENT*1} this inference round added {delta} more implied stmts')
        log.info(f'{INDENT*0} {len(implied)} stmts implied:')
        for st in implied:
            log.info(f'{INDENT*2} {st}')
        return implied

    def _iterateAllRules(self, workingSet: Graph, implied: Graph):
        for i, r in enumerate(self.rules):
            log.debug('')
            log.debug(f'{INDENT*2} workingSet:')
            for i, stmt in enumerate(sorted(workingSet)):
                log.debug(f'{INDENT*3} ({i}) {stmt}')

            log.debug('')
            log.debug(f'{INDENT*2}-applying rule {i}')
            log.debug(f'{INDENT*3} rule def lhs: {graphDump(r[0])}')
            log.debug(f'{INDENT*3} rule def rhs: {graphDump(r[2])}')
            if r[1] == LOG['implies']:
                applyRule(Lhs(r[0]), r[2], workingSet, implied)
            else:
                log.info(f'{INDENT*2} {r} not a rule?')


def applyRule(lhs: Lhs, rhs: Graph, workingSet: Graph, implied: Graph):
    for binding in lhs.findCandidateBindings(ReadOnlyGraphAggregate([workingSet])):
        # log.debug(f'        rule gave {binding=}')
        for lhsBoundStmt in binding.apply(lhs.graphWithoutEvals(binding)):
            workingSet.add(lhsBoundStmt)
        for newStmt in binding.apply(rhs):
            workingSet.add(newStmt)
            implied.add(newStmt)


def parseList(graph, subj) -> Tuple[List[Node], Set[Triple]]:
    """"Do like Collection(g, subj) but also return all the 
    triples that are involved in the list"""
    out = []
    used = set()
    cur = subj
    while True:
        # bug: mishandles empty list
        out.append(graph.value(cur, RDF.first))
        used.add((cur, RDF.first, out[-1]))

        next = graph.value(cur, RDF.rest)
        used.add((cur, RDF.rest, next))

        cur = next
        if cur == RDF.nil:
            break
    return out, used


def graphDump(g: Union[Graph, List[Triple]]):
    if not isinstance(g, Graph):
        g2 = Graph()
        for stmt in g:
            g2.add(stmt)
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


def isStatic(spo: Triple):
    for t in spo:
        if isinstance(t, (Variable, BNode)):
            return False
    return True
