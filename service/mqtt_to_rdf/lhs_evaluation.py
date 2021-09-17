from dataclasses import dataclass
import logging
from decimal import Decimal
from candidate_binding import CandidateBinding
from typing import Dict, Iterator, List, Optional, Set, Tuple, Type, Union, cast

from prometheus_client import Summary
from rdflib import RDF, Literal, Namespace, URIRef
from rdflib.graph import Graph
from rdflib.term import BNode, Node, Variable

from inference_types import BindableTerm, Triple

log = logging.getLogger('infer')

INDENT = '    '

ROOM = Namespace("http://projects.bigasterisk.com/room/")
LOG = Namespace('http://www.w3.org/2000/10/swap/log#')
MATH = Namespace('http://www.w3.org/2000/10/swap/math#')


def numericNode(n: Node):
    if not isinstance(n, Literal):
        raise TypeError(f'expected Literal, got {n=}')
    val = n.toPython()
    if not isinstance(val, (int, float, Decimal)):
        raise TypeError(f'expected number, got {val=}')
    return val


def parseList(graph, subj) -> Tuple[List[Node], Set[Triple]]:
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


registeredFunctionTypes: List[Type['Function']] = []


def register(cls: Type['Function']):
    registeredFunctionTypes.append(cls)
    return cls


class Function:
    """any rule stmt that runs a function (not just a statement match)"""
    pred: URIRef

    def __init__(self, stmt: Triple, ruleGraph: Graph):
        self.stmt = stmt
        if stmt[1] != self.pred:
            raise TypeError
        self.ruleGraph = ruleGraph

    def getOperandNodes(self, existingBinding: CandidateBinding) -> List[Node]:
        raise NotImplementedError

    def getNumericOperands(self, existingBinding: CandidateBinding) -> List[Union[int, float, Decimal]]:
        out = []
        for op in self.getOperandNodes(existingBinding):
            out.append(numericNode(op))

        return out

    def bind(self, existingBinding: CandidateBinding) -> Optional[CandidateBinding]:
        """either any new bindings this function makes (could be 0), or None if it doesn't match"""
        raise NotImplementedError

    def valueInObjectTerm(self, value: Node) -> Optional[CandidateBinding]:
        objVar = self.stmt[2]
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
        return [existingBinding.applyTerm(self.stmt[0])]


class SubjectObjectFunction(Function):
    """a filter function that depends on the subject and object terms"""

    def getOperandNodes(self, existingBinding: CandidateBinding) -> List[Node]:
        return [existingBinding.applyTerm(self.stmt[0]), existingBinding.applyTerm(self.stmt[2])]


class ListFunction(Function):
    """function that takes an rdf list as input"""

    def usedStatements(self) -> Set[Triple]:
        _, used = parseList(self.ruleGraph, self.stmt[0])
        return used

    def getOperandNodes(self, existingBinding: CandidateBinding) -> List[Node]:
        operands, _ = parseList(self.ruleGraph, self.stmt[0])
        return [existingBinding.applyTerm(x) for x in operands]


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

### registration is done

_byPred: Dict[URIRef, Type[Function]] = dict((cls.pred, cls) for cls in registeredFunctionTypes)
def functionsFor(pred: URIRef) -> Iterator[Type[Function]]:
    try:
        yield _byPred[pred]
    except KeyError:
        return


def lhsStmtsUsedByFuncs(graph: Graph) -> Set[Triple]:
    usedByFuncs: Set[Triple] = set()  # don't worry about matching these
    for s in graph:
        for cls in functionsFor(pred=s[1]):
            usedByFuncs.update(cls(s, graph).usedStatements())
    return usedByFuncs


def rulePredicates() -> Set[URIRef]:
    return set(c.pred for c in registeredFunctionTypes)