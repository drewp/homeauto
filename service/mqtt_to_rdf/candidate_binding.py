from dataclasses import dataclass
from typing import Dict, Iterator

from prometheus_client import Summary
from rdflib import BNode, Graph
from rdflib.term import Node, Variable

from inference_types import BindableTerm, BindingUnknown, Triple


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

    def addNewBindings(self, newBindings: 'CandidateBinding'):
        for k, v in newBindings.binding.items():
            if k in self.binding and self.binding[k] != v:
                raise ValueError(
                    f'conflict- thought {k} would be {self.binding[k]} but another Evaluation said it should be {v}')
            self.binding[k] = v