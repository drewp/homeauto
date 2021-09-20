"""
Some of these are from https://www.w3.org/2000/10/swap/doc/CwmBuiltins
"""
import urllib.parse
from decimal import Decimal
from typing import Optional, cast

from rdflib import Literal, Namespace, URIRef

from candidate_binding import CandidateBinding
from lhs_evaluation import (ListFunction, SubjectFunction, SubjectObjectFunction, register)

MATH = Namespace('http://www.w3.org/2000/10/swap/math#')
ROOM = Namespace("http://projects.bigasterisk.com/room/")


@register
class Gt(SubjectObjectFunction):
    pred = MATH['greaterThan']

    def bind(self, existingBinding: CandidateBinding) -> Optional[CandidateBinding]:
        [x, y] = self.getNumericOperands(existingBinding)
        if x > y:
            return CandidateBinding({})  # no new values; just allow matching to keep going


@register
class AsFarenheit(SubjectFunction):
    pred = ROOM['asFarenheit']

    def bind(self, existingBinding: CandidateBinding) -> Optional[CandidateBinding]:
        [x] = self.getNumericOperands(existingBinding)
        f = cast(Literal, Literal(Decimal(x) * 9 / 5 + 32))
        return self.valueInObjectTerm(f)


@register
class Sum(ListFunction):
    pred = MATH['sum']

    def bind(self, existingBinding: CandidateBinding) -> Optional[CandidateBinding]:
        f = Literal(sum(self.getNumericOperands(existingBinding)))
        return self.valueInObjectTerm(f)


@register
class ChildResource(ListFunction):
    pred = ROOM['childResource']

    def bind(self, existingBinding: CandidateBinding) -> Optional[CandidateBinding]:
        ops = self.getOperandNodes(existingBinding)
        if len(ops) != 2 or not isinstance(ops[0], URIRef) or not isinstance(ops[1], Literal):
            raise ValueError(f'expected (?baseUri ?nextSegmentString) as subject to {self}')
        newUri = URIRef(ops[0].rstrip('/') + '/' + urllib.parse.quote(ops[1].toPython(), safe=''))
        return self.valueInObjectTerm(newUri)
