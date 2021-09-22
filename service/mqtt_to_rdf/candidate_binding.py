import logging
from dataclasses import dataclass
from typing import Dict, Iterator

from prometheus_client import Summary
from rdflib import BNode, Graph
from rdflib.term import Node, Variable

from inference_types import BindableTerm, BindingUnknown, Triple

log = logging.getLogger('cbind')
INDENT = '    '


class BindingConflict(ValueError):  # might be the same as `Inconsistent`
    pass


@dataclass
class CandidateBinding:
    binding: Dict[BindableTerm, Node]

    def __repr__(self):
        b = " ".join("%r=%r" % (var, value) for var, value in sorted(self.binding.items()))
        return f'CandidateBinding({b})'

    def apply(self, g: Graph, returnBoundStatementsOnly=True) -> Iterator[Triple]:
        for stmt in g:
            try:
                bound = (
                    self.applyTerm(stmt[0], returnBoundStatementsOnly),  #
                    self.applyTerm(stmt[1], returnBoundStatementsOnly),  #
                    self.applyTerm(stmt[2], returnBoundStatementsOnly))
            except BindingUnknown:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f'{INDENT*7} CB.apply cant bind {stmt} using {self.binding}')

                continue
            if log.isEnabledFor(logging.DEBUG):
                log.debug(f'{INDENT*7} CB.apply took {stmt} to {bound}')

            yield bound

    def applyTerm(self, term: Node, failUnbound=True):
        if isinstance(term, (Variable, BNode)):
            if term in self.binding:
                return self.binding[term]
            else:
                if failUnbound:
                    raise BindingUnknown()
        return term

    def addNewBindings(self, newBindings: 'CandidateBinding'):
        for k, v in newBindings.binding.items():
            if k in self.binding and self.binding[k] != v:
                raise BindingConflict(f'thought {k} would be {self.binding[k]} but another Evaluation said it should be {v}')
            self.binding[k] = v

    def copy(self):
        return CandidateBinding(self.binding.copy())

    def contains(self, term: BindableTerm):
        return term in self.binding
