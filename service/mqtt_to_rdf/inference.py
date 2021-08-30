"""
copied from reasoning 2021-08-29. probably same api. should
be able to lib/ this out
"""

import logging
from typing import Dict, Tuple
from dataclasses import dataclass
from prometheus_client import Summary
from rdflib import Graph, Namespace
from rdflib.graph import ConjunctiveGraph
from rdflib.term import Node, Variable

log = logging.getLogger('infer')

Triple = Tuple[Node, Node, Node]
Rule = Tuple[Graph, Node, Graph]

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

        workingSet = ConjunctiveGraph()
        if isinstance(graph, ConjunctiveGraph):
            workingSet.addN(graph.quads())
        else:
            for triple in graph:
                workingSet.add(triple)

        implied = ConjunctiveGraph()

        bailout_iterations = 100
        delta = 1
        while delta > 0 and bailout_iterations > 0:
            bailout_iterations -= 1
            delta = -len(implied)
            self._iterateRules(workingSet, implied)
            delta += len(implied)
            log.info(f'  this inference round added {delta} more implied stmts')
        log.info(f'{len(implied)} stmts implied:')
        for st in implied:
            log.info(f'  {st}')
        return implied

    def _iterateRules(self, workingSet, implied):
        for r in self.rules:
            if r[1] == LOG['implies']:
                self._applyRule(r[0], r[2], workingSet, implied)
            else:
                log.info(f'  {r} not a rule?')

    def _applyRule(self, lhs, rhs, workingSet, implied):
        containsSetup = self._containsSetup(lhs, workingSet)
        if containsSetup:
            for st in rhs:
                workingSet.add(st)
                implied.add(st)

    def _containsSetup(self, lhs, workingSet):
        return all(st in workingSet for st in lhs)
