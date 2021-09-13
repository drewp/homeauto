import logging
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Union

from prometheus_client import Summary
from rdflib import BNode, Graph
from rdflib.term import Node, Variable

from inference_types import BindableTerm, BindingUnknown, Triple
log = logging.getLogger()
INDENT = '    '

@dataclass
class CandidateBinding:
    binding: Dict[BindableTerm, Node]

    def __repr__(self):
        b = " ".join("%s=%s" % (k, v) for k, v in sorted(self.binding.items()))
        return f'CandidateBinding({b})'

    def apply(self, g: Union[Graph, Iterable[Triple]], returnBoundStatementsOnly=True) -> Iterator[Triple]:
        for stmt in g:
            try:
                bound = (
                    self._applyTerm(stmt[0], returnBoundStatementsOnly), 
                    self._applyTerm(stmt[1], returnBoundStatementsOnly), 
                    self._applyTerm(stmt[2], returnBoundStatementsOnly))
            except BindingUnknown:
                log.debug(f'{INDENT*7} CB.apply cant bind {stmt} using {self.binding}')

                continue
            log.debug(f'{INDENT*7} CB.apply took {stmt} to {bound}')

            yield bound

    def _applyTerm(self, term: Node, failUnbound=True):
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
                raise ValueError(f'conflict- thought {k} would be {self.binding[k]} but another Evaluation said it should be {v}')
            self.binding[k] = v
