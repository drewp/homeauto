import logging
from decimal import Decimal
from typing import (Dict, Iterator, List, Optional, Set, Tuple, Type, Union, cast)

from prometheus_client import Summary
from rdflib import RDF, Literal, Namespace, URIRef
from rdflib.term import Node, Variable

from candidate_binding import CandidateBinding
from inference_types import BindableTerm, Triple
from stmt_chunk import Chunk, ChunkedGraph

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


def _parseList(graph: ChunkedGraph, subj: Node) -> Tuple[List[Node], Set[Triple]]:
    """"Do like Collection(g, subj) but also return all the 
    triples that are involved in the list"""
    out = []
    used = set()
    cur = subj
    while cur != RDF.nil:
        elem = graph.value(cur, RDF.first)
        if elem is None:
            raise ValueError('bad list')
        out.append(elem)
        used.add((cur, RDF.first, out[-1]))

        next = graph.value(cur, RDF.rest)
        if next is None:
            raise ValueError('bad list')
        used.add((cur, RDF.rest, next))

        cur = next
    return out, used


_registeredFunctionTypes: List[Type['Function']] = []


def register(cls: Type['Function']):
    _registeredFunctionTypes.append(cls)
    return cls


class Function:
    """any rule stmt that runs a function (not just a statement match)"""
    pred: URIRef

    def __init__(self, chunk: Chunk, ruleGraph: ChunkedGraph):
        self.chunk = chunk
        if chunk.predicate != self.pred:
            raise TypeError
        self.ruleGraph = ruleGraph

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

    def usedStatements(self) -> Set[Triple]:
        '''stmts in self.graph (not including self.stmt, oddly) that are part of
        this function setup and aren't to be matched literally'''
        return set()


class SubjectFunction(Function):
    """function that depends only on the subject term"""

    def getOperandNodes(self, existingBinding: CandidateBinding) -> List[Node]:
        return [existingBinding.applyTerm(self.chunk.primary[0])]


class SubjectObjectFunction(Function):
    """a filter function that depends on the subject and object terms"""

    def getOperandNodes(self, existingBinding: CandidateBinding) -> List[Node]:
        return [existingBinding.applyTerm(self.chunk.primary[0]), existingBinding.applyTerm(self.chunk.primary[2])]


class ListFunction(Function):
    """function that takes an rdf list as input"""

    def usedStatements(self) -> Set[Triple]:
        _, used = _parseList(self.ruleGraph, self.chunk.primary[0])
        return used

    def getOperandNodes(self, existingBinding: CandidateBinding) -> List[Node]:
        operands, _ = _parseList(self.ruleGraph, self.chunk.primary[0])
        return [existingBinding.applyTerm(x) for x in operands]

import inference_functions # calls register() on some classes

_byPred: Dict[URIRef, Type[Function]] = dict((cls.pred, cls) for cls in _registeredFunctionTypes)


def functionsFor(pred: URIRef) -> Iterator[Type[Function]]:
    try:
        yield _byPred[pred]
    except KeyError:
        return


# def lhsStmtsUsedByFuncs(graph: ChunkedGraph) -> Set[Chunk]:
#     usedByFuncs: Set[Triple] = set()  # don't worry about matching these
#     for s in graph:
#         for cls in functionsFor(pred=s[1]):
#             usedByFuncs.update(cls(s, graph).usedStatements())
#     return usedByFuncs


def rulePredicates() -> Set[URIRef]:
    return set(c.pred for c in _registeredFunctionTypes)
