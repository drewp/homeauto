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


class Inference:

    def __init__(self) -> None:
        self.rules = ConjunctiveGraph()

    def setRules(self, g: ConjunctiveGraph):
        self.rules = g

    def infer(self, graph: Graph):
        """
        returns new graph of inferred statements.
        """
        log.info(f'Begin inference of graph len={len(graph)} with rules len={len(self.rules)}:')

        # everything that is true: the input graph, plus every rule conclusion we can make
        workingSet = graphCopy(graph)

        # just the statements that came from rule RHS's.
        implied = ConjunctiveGraph()

        bailout_iterations = 100
        delta = 1
        while delta > 0 and bailout_iterations > 0:
            log.debug(f'  * iteration ({bailout_iterations} left)')
            bailout_iterations -= 1
            delta = -len(implied)
            self._iterateAllRules(workingSet, implied)
            delta += len(implied)
            log.info(f'  this inference round added {delta} more implied stmts')
        log.info(f'    {len(implied)} stmts implied:')
        for st in implied:
            log.info(f'        {st}')
        return implied

    def _iterateAllRules(self, workingSet, implied):
        for i, r in enumerate(self.rules):
            log.debug(f'      workingSet: {graphDump(workingSet)}')
            log.debug(f'      - applying rule {i}')
            log.debug(f'        lhs: {graphDump(r[0])}')
            log.debug(f'        rhs: {graphDump(r[2])}')
            if r[1] == LOG['implies']:
                applyRule(r[0], r[2], workingSet, implied)
            else:
                log.info(f'   {r} not a rule?')


def graphCopy(src: Graph) -> Graph:
    if isinstance(src, ConjunctiveGraph):
        out = ConjunctiveGraph()
        out.addN(src.quads())
        return out
    else:
        out = Graph()
        for triple in src:
            out.add(triple)
        return out


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


def applyRule(lhs: Graph, rhs: Graph, workingSet: Graph, implied: Graph):
    for bindings in findCandidateBindings(lhs, workingSet):
        log.debug(f'        rule gave {bindings=}')
        for lhsBoundStmt in withBinding(lhs, bindings):
            workingSet.add(lhsBoundStmt)
        for newStmt in withBinding(rhs, bindings):
            workingSet.add(newStmt)
            implied.add(newStmt)


def findCandidateBindings(lhs: Graph, workingSet: Graph) -> Iterator[Dict[BindableTerm, Node]]:
    """bindings that fit the LHS of a rule, using statements from workingSet and functions
    from LHS"""
    varsToBind: Set[BindableTerm] = set()
    staticRuleStmts = Graph()
    for ruleStmt in lhs:
        varsInStmt = [v for v in ruleStmt if isinstance(v, (Variable, BNode))]
        varsToBind.update(varsInStmt)
        if (not varsInStmt  # ok
                #and not any(isinstance(t, BNode) for t in ruleStmt)  # approx
           ):
            staticRuleStmts.add(ruleStmt)

    log.debug(f'        varsToBind: {sorted(varsToBind)}')

    if someStaticStmtDoesntMatch(staticRuleStmts, workingSet):
        log.debug(f'    someStaticStmtDoesntMatch: {graphDump(staticRuleStmts)}')
        return

    # the total set of terms each variable could possibly match
    candidateTermMatches: Dict[BindableTerm, Set[Node]] = findCandidateTermMatches(lhs, workingSet)

    orderedVars, orderedValueSets = organize(candidateTermMatches)

    log.debug(f'        candidate terms:')
    log.debug(f'            {orderedVars=}')
    log.debug(f'            {orderedValueSets=}')

    for i, perm in enumerate(itertools.product(*orderedValueSets)):
        binding: Dict[BindableTerm, Node] = dict(zip(orderedVars, perm))
        log.debug('')
        log.debug(f'            ** trying {binding=}')
        usedByFuncs = Graph()
        for v, val, used in inferredFuncBindings(lhs, binding):  # loop this until it's done
            log.debug(f'            inferredFuncBindings tells us {v}={val}')
            binding[v] = val
            usedByFuncs += used
        if len(binding) != len(varsToBind):
            log.debug(f'                binding is incomplete, needs {varsToBind}')

            continue
        if not verifyBinding(lhs, binding, workingSet, usedByFuncs):  # fix this
            log.debug(f'            this binding did not verify')
            continue
        yield binding


def inferredFuncBindings(lhs: Graph, bindingsBefore) -> Iterator[Tuple[Variable, Node, Graph]]:
    for stmt in lhs:
        if stmt[1] not in inferredFuncs:
            continue
        var = stmt[2]
        if not isinstance(var, Variable):
            continue

        x = stmt[0]
        if isinstance(x, Variable):
            x = bindingsBefore[x]

        resultObject, usedByFunc = inferredFuncObject(x, stmt[1], lhs, bindingsBefore)

        yield var, resultObject, usedByFunc


def findCandidateTermMatches(lhs: Graph, workingSet: Graph) -> Dict[BindableTerm, Set[Node]]:
    candidateTermMatches: Dict[BindableTerm, Set[Node]] = defaultdict(set)
    lhsBnodes: Set[BNode] = set()
    for lhsStmt in lhs:
        for trueStmt in workingSet:
            log.debug(f'            lhsStmt={graphDump([lhsStmt])} trueStmt={graphDump([trueStmt])}')
            bindingsFromStatement: Dict[Variable, Set[Node]] = {}
            for lhsTerm, trueTerm in zip(lhsStmt, trueStmt):
                # log.debug(f' test {lhsTerm=} {trueTerm=}')
                if isinstance(lhsTerm, BNode):
                    lhsBnodes.add(lhsTerm)
                elif isinstance(lhsTerm, Variable):
                    bindingsFromStatement.setdefault(lhsTerm, set()).add(trueTerm)
                elif lhsTerm != trueTerm:
                    break
            else:
                for v, vals in bindingsFromStatement.items():
                    candidateTermMatches[v].update(vals)

    for trueStmt in itertools.chain(workingSet, lhs):
        for b in lhsBnodes:
            for t in [trueStmt[0], trueStmt[2]]:
                if isinstance(t, (URIRef, BNode)):
                    candidateTermMatches[b].add(t)
    return candidateTermMatches


def withBinding(toBind: Graph, bindings: Dict[BindableTerm, Node], includeStaticStmts=True) -> Iterator[Triple]:
    for stmt in toBind:
        stmt = list(stmt)
        static = True
        for i, term in enumerate(stmt):
            if isinstance(term, (Variable, BNode)):
                stmt[i] = bindings[term]
                static = False
        else:
            if includeStaticStmts or not static:
                yield cast(Triple, stmt)


def verifyBinding(lhs: Graph, binding: Dict[BindableTerm, Node], workingSet: Graph, usedByFuncs: Graph) -> bool:
    """Can this lhs be true all at once in workingSet? Does it match with these bindings?"""
    log.debug(f'                verify all bindings against this lhs:')
    boundLhs = list(withBinding(lhs, binding))
    for stmt in boundLhs:
        log.debug(f'                    {stmt}')

    log.debug(f'                and against this workingSet:')
    for stmt in workingSet:
        log.debug(f'                    {stmt}')

    log.debug(f'                ignoring these usedByFuncs:')
    boundUsedByFuncs = list(withBinding(usedByFuncs, binding))
    for stmt in boundUsedByFuncs:
        log.debug(f'                    {stmt}')
    # The static stmts in lhs are obviously going
    # to match- we only need to verify the ones
    # that needed bindings.
    for stmt in boundLhs:  #withBinding(lhs, binding, includeStaticStmts=False):
        log.debug(f'                check for {stmt}')

        if stmt[1] in filterFuncs:
            if not mathTest(*stmt):
                log.debug(f'                    binding was invalid because {stmt}) is not true')
                return False
        elif stmt in boundUsedByFuncs:
            pass
        elif stmt in workingSet:
            pass
        else:
            log.debug(f'                    binding was invalid because {stmt}) cannot be true')
            return False
    return True


inferredFuncs = {
    ROOM['asFarenheit'],
    MATH['sum'],
}
filterFuncs = {
    MATH['greaterThan'],
}


def isStatic(spo: Triple):
    for t in spo:
        if isinstance(t, (Variable, BNode)):
            return False
    return True


def inferredFuncObject(subj, pred, graph, bindings) -> Tuple[Literal, Graph]:
    """return result from like `(1 2) math:sum ?out .` plus a graph of all the
    statements involved in that function rule (including the bound answer"""
    used = Graph()
    if pred == ROOM['asFarenheit']:
        obj = Literal(Decimal(subj.toPython()) * 9 / 5 + 32)
    elif pred == MATH['sum']:
        operands, operandsStmts = parseList(graph, subj)
        # shouldn't be redoing this here
        operands = [bindings[o] if isinstance(o, Variable) else o for o in operands]
        log.debug(f'                sum {[op.toPython() for op in operands]}')
        used += operandsStmts
        obj = Literal(sum(op.toPython() for op in operands))
    else:
        raise NotImplementedError(pred)

    used.add((subj, pred, obj))
    return obj, used


def parseList(graph, subj) -> Tuple[List[Node], Set[Triple]]:
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


def mathTest(subj, pred, obj):
    x = subj.toPython()
    y = obj.toPython()
    if pred == MATH['greaterThan']:
        return x > y
    else:
        raise NotImplementedError(pred)


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


def someStaticStmtDoesntMatch(staticRuleStmts, workingSet):
    for ruleStmt in staticRuleStmts:
        if ruleStmt not in workingSet:
            log.debug(f'            {ruleStmt} not in working set- skip rule')

            return True
    return False
