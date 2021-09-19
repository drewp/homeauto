from typing import Tuple, Union

from rdflib import Graph
from rdflib.graph import ReadOnlyGraphAggregate
from rdflib.term import BNode, Node, Variable

BindableTerm = Union[Variable, BNode]
ReadOnlyWorkingSet = ReadOnlyGraphAggregate
Triple = Tuple[Node, Node, Node]


class EvaluationFailed(ValueError):
    """e.g. we were given (5 math:greaterThan 6)"""


class BindingUnknown(ValueError):
    """e.g. we were asked to make the bound version 
    of (A B ?c) and we don't have a binding for ?c
    """


class Inconsistent(ValueError):
    """adding this stmt would be inconsistent with an existing binding"""
