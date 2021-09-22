import logging
from decimal import Decimal
from typing import Dict, Iterator, List, Optional, Type, Union, cast

from rdflib import Literal, Namespace, URIRef
from rdflib.term import Node, Variable

from candidate_binding import CandidateBinding
from inference_types import BindableTerm
from stmt_chunk import Chunk

log = logging.getLogger('infer')

INDENT = '    '

ROOM = Namespace("http://projects.bigasterisk.com/room/")
LOG = Namespace('http://www.w3.org/2000/10/swap/log#')
MATH = Namespace('http://www.w3.org/2000/10/swap/math#')


def _numericNode(n: Node):
    if not isinstance(n, Literal):
        raise TypeError(f'expected Literal, got {n=}')
    val = n.toPython()
    if not isinstance(val, (int, float, Decimal)):
        raise TypeError(f'expected number, got {val=}')
    return val


class Function:
    """any rule stmt that runs a function (not just a statement match)"""
    pred: URIRef

    def __init__(self, chunk: Chunk):
        self.chunk = chunk
        if chunk.predicate != self.pred:
            raise TypeError

    def getOperandNodes(self, existingBinding: CandidateBinding) -> List[Node]:
        raise NotImplementedError

    def getNumericOperands(self, existingBinding: CandidateBinding) -> List[Union[int, float, Decimal]]:
        out = []
        for op in self.getOperandNodes(existingBinding):
            out.append(_numericNode(op))

        return out

    def bind(self, existingBinding: CandidateBinding) -> Optional[CandidateBinding]:
        """either any new bindings this function makes (could be 0), or None if it doesn't match"""
        raise NotImplementedError

    def valueInObjectTerm(self, value: Node) -> Optional[CandidateBinding]:
        objVar = self.chunk.primary[2]
        if not isinstance(objVar, Variable):
            raise TypeError(f'expected Variable, got {objVar!r}')
        return CandidateBinding({cast(BindableTerm, objVar): value})


class SubjectFunction(Function):
    """function that depends only on the subject term"""

    def getOperandNodes(self, existingBinding: CandidateBinding) -> List[Node]:
        if self.chunk.primary[0] is None:
            raise ValueError(f'expected one operand on {self.chunk}')
        return [existingBinding.applyTerm(self.chunk.primary[0])]


class SubjectObjectFunction(Function):
    """a filter function that depends on the subject and object terms"""

    def getOperandNodes(self, existingBinding: CandidateBinding) -> List[Node]:
        if self.chunk.primary[0] is None or self.chunk.primary[2] is None:
            raise ValueError(f'expected one operand on each side of {self.chunk}')
        return [existingBinding.applyTerm(self.chunk.primary[0]), existingBinding.applyTerm(self.chunk.primary[2])]


class ListFunction(Function):
    """function that takes an rdf list as input"""

    def getOperandNodes(self, existingBinding: CandidateBinding) -> List[Node]:
        if self.chunk.subjList is None:
            raise ValueError(f'expected subject list on {self.chunk}')
        return [existingBinding.applyTerm(x) for x in self.chunk.subjList]


_registeredFunctionTypes: List[Type['Function']] = []


def register(cls: Type['Function']):
    _registeredFunctionTypes.append(cls)
    return cls


import inference_functions  # calls register() on some classes

_byPred: Dict[URIRef, Type[Function]] = dict((cls.pred, cls) for cls in _registeredFunctionTypes)


def functionsFor(pred: URIRef) -> Iterator[Type[Function]]:
    try:
        yield _byPred[pred]
    except KeyError:
        return
