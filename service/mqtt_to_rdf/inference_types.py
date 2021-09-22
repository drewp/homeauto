from typing import NewType, Tuple, Union

from rdflib.graph import ReadOnlyGraphAggregate
from rdflib.term import BNode, Node, Variable

ReadOnlyWorkingSet = ReadOnlyGraphAggregate
Triple = Tuple[Node, Node, Node]

# BNode subclasses:
# It was easy to make mistakes with BNodes in rules, since unlike a
# Variable('x') obviously turning into a URIRef('foo') when it gets bound, an
# unbound BNode sometimes turns into another BNode. Sometimes a rule statement
# would contain a mix of those, leading to errors in deciding what's still a
# BindableTerm.


class RuleUnboundBnode(BNode):
    pass


class RuleBoundBnode(BNode):
    pass


class RuleOutBnode(BNode):
    """bnode coming out of a valid rule binding. Needs remapping to distinct
    implied-graph bnodes"""


class RhsBnode(BNode):
    pass


# Just an alias so I can stop importing BNode elsewhere and have to use a
# clearer type name.
WorkingSetBnode = BNode

BindableTerm = Union[Variable, RuleUnboundBnode]


class EvaluationFailed(ValueError):
    """e.g. we were given (5 math:greaterThan 6)"""


class BindingUnknown(ValueError):
    """e.g. we were asked to make the bound version of (A B ?c) and we don't
    have a binding for ?c
    """


class Inconsistent(ValueError):
    """adding this stmt would be inconsistent with an existing binding"""
