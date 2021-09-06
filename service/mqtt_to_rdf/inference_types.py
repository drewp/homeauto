from typing import Tuple, Union
from rdflib import Graph
from rdflib.term import Node, BNode, Variable
from rdflib.graph import ReadOnlyGraphAggregate

BindableTerm = Union[Variable, BNode]
ReadOnlyWorkingSet = ReadOnlyGraphAggregate
Triple = Tuple[Node, Node, Node]


class EvaluationFailed(ValueError):
    """e.g. we were given (5 math:greaterThan 6)"""


class BindingUnknown(ValueError):
    """e.g. we were asked to make the bound version 
    of (A B ?c) and we don't have a binding for ?c
    """
