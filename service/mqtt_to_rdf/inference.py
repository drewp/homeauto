"""
copied from reasoning 2021-08-29. probably same api. should
be able to lib/ this out
"""
import itertools
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterator, List, Set, Tuple, Union, cast
from urllib.request import OpenerDirector

from prometheus_client import Summary
from rdflib import BNode, Graph, Literal, Namespace
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


def graphDump(g: Graph):
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


def findCandidateBindings(lhs: Graph, workingSet: Graph) -> Iterator[Dict[Variable, Node]]:
    """bindings that fit the LHS of a rule, using statements from workingSet and functions
    from LHS"""
    varsToBind: Set[Variable] = set()
    staticRuleStmts = Graph()
    for ruleStmt in lhs:
        varsInStmt = [v for v in ruleStmt if isinstance(v, Variable)]
        varsToBind.update(varsInStmt)
        if (not varsInStmt  # ok
                #and not any(isinstance(t, BNode) for t in ruleStmt)  # approx
           ):
            staticRuleStmts.add(ruleStmt)

    log.debug(f'        {varsToBind=}')

    if someStaticStmtDoesntMatch(staticRuleStmts, workingSet):
        log.debug(f'    someStaticStmtDoesntMatch: {graphDump(staticRuleStmts)}')
        return

    # the total set of terms each variable could possibly match
    candidateTermMatches: Dict[Variable, Set[Node]] = findCandidateTermMatches(lhs, workingSet)

    orderedVars, orderedValueSets = organize(candidateTermMatches)

    log.debug(f'        candidate terms:')
    log.debug(f'            {orderedVars=}')
    log.debug(f'            {orderedValueSets=}')

    for perm in itertools.product(*orderedValueSets):
        binding: Dict[Variable, Node] = dict(zip(orderedVars, perm))
        log.debug(f'            {binding=} but lets look for funcs')
        for v, val in inferredFuncBindings(lhs, binding):  # loop this until it's done
            log.debug(f'        ifb tells us {v}={val}')
            binding[v] = val
        if not verifyBinding(lhs, binding, workingSet):  # fix this
            log.debug(f'        verify culls')
            continue
        yield binding


def inferredFuncBindings(lhs: Graph, bindingsBefore) -> Iterator[Tuple[Variable, Node]]:
    for stmt in lhs:
        if stmt[1] not in inferredFuncs:
            continue
        if not isinstance(stmt[2], Variable):
            continue

        x = stmt[0]
        if isinstance(x, Variable):
            x = bindingsBefore[x]
        yield stmt[2], inferredFuncObject(x, stmt[1], lhs, bindingsBefore)


def findCandidateTermMatches(lhs: Graph, workingSet: Graph) -> Dict[Variable, Set[Node]]:
    candidateTermMatches: Dict[Variable, Set[Node]] = {}

    for lhsStmt in lhs:
        for trueStmt in workingSet:
            log.debug(f'{lhsStmt=} {trueStmt=}')
            bindingsFromStatement: Dict[Variable, Set[Node]] = {}
            for lhsTerm, trueTerm in zip(lhsStmt, trueStmt):
                log.debug(f' test {lhsTerm=} {trueTerm=}')
                if isinstance(lhsTerm, Variable):
                    bindingsFromStatement.setdefault(lhsTerm, set()).add(trueTerm)
                elif lhsTerm != trueTerm:
                    break
            else:
                for v, vals in bindingsFromStatement.items():
                    candidateTermMatches.setdefault(v, set()).update(vals)
    return candidateTermMatches


def withBinding(rhs: Graph, bindings: Dict[Variable, Node]) -> Iterator[Triple]:
    for stmt in rhs:
        stmt = list(stmt)
        for i, t in enumerate(stmt):
            if isinstance(t, Variable):
                try:
                    stmt[i] = bindings[t]
                except KeyError:
                    # stmt is from another rule that we're not applying right now
                    break
        else:
            yield cast(Triple, stmt)


def verifyBinding(lhs: Graph, binding: Dict[Variable, Node], workingSet: Graph) -> bool:
    """can this lhs be true all at once?"""
    for stmt in withBinding(lhs, binding):
        log.debug(f'    lhs verify {stmt}')
        if stmt[1] in filterFuncs:
            if not mathTest(*stmt):
                return False
        elif (stmt not in workingSet  # not previously true
              and stmt not in lhs  # not from the bindings in this rule
              and stmt[1] not in inferredFuncs  # not a function stmt (maybe this is wrong)
             ):
            log.debug(f'    ver culls here')
            return False
    return True


inferredFuncs = {
    ROOM['asFarenheit'],
    MATH['sum'],
}
filterFuncs = {
    MATH['greaterThan'],
}


def inferredFuncObject(subj, pred, graph, bindings):
    if pred == ROOM['asFarenheit']:
        return Literal(Decimal(subj.toPython()) * 9 / 5 + 32)
    elif pred == MATH['sum']:
        operands = Collection(graph, subj)
        # shouldn't be redoing this here
        operands = [bindings[o] if isinstance(o, Variable) else o for o in operands]
        log.debug(f' sum {list(operands)}')
        return Literal(sum(op.toPython() for op in operands))

    else:
        raise NotImplementedError(pred)


def mathTest(subj, pred, obj):
    x = subj.toPython()
    y = obj.toPython()
    if pred == MATH['greaterThan']:
        return x > y
    else:
        raise NotImplementedError(pred)


def organize(candidateTermMatches: Dict[Variable, Set[Node]]) -> Tuple[List[Variable], List[List[Node]]]:
    items = list(candidateTermMatches.items())
    items.sort()
    orderedVars: List[Variable] = []
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
