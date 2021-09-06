import logging
from decimal import Decimal
from typing import Dict, Iterable, Iterator, List, Set, Tuple

from prometheus_client import Summary
from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.term import Node, Variable

from candidate_binding import CandidateBinding
from inference import CandidateBinding
from inference_types import BindableTerm, EvaluationFailed, Triple

log = logging.getLogger('infer')

INDENT = '    '

ROOM = Namespace("http://projects.bigasterisk.com/room/")
LOG = Namespace('http://www.w3.org/2000/10/swap/log#')
MATH = Namespace('http://www.w3.org/2000/10/swap/math#')

# Graph() makes a BNode if you don't pass
# identifier, which can be a bottleneck.
GRAPH_ID = URIRef('dont/care')


# alternate name LhsComponent
class Evaluation:
    """some lhs statements need to be evaluated with a special function 
    (e.g. math) and then not considered for the rest of the rule-firing 
    process. It's like they already 'matched' something, so they don't need
    to match a statement from the known-true working set.
    
    One Evaluation instance is for one function call.
    """

    @staticmethod
    def findEvals(graph: Graph) -> Iterator['Evaluation']:
        for stmt in graph.triples((None, MATH['sum'], None)):
            operands, operandsStmts = _parseList(graph, stmt[0])
            yield Evaluation(operands, stmt, operandsStmts)

        for stmt in graph.triples((None, MATH['greaterThan'], None)):
            yield Evaluation([stmt[0], stmt[2]], stmt, [])

        for stmt in graph.triples((None, ROOM['asFarenheit'], None)):
            yield Evaluation([stmt[0]], stmt, [])

    # internal, use findEvals
    def __init__(self, operands: List[Node], mainStmt: Triple, otherStmts: Iterable[Triple]) -> None:
        self.operands = operands
        self.operandsStmts = Graph(identifier=GRAPH_ID)
        self.operandsStmts += otherStmts  # may grow
        self.operandsStmts.add(mainStmt)
        self.stmt = mainStmt

    def resultBindings(self, inputBindings: CandidateBinding) -> Tuple[CandidateBinding, Graph]:
        """under the bindings so far, what would this evaluation tell us, and which stmts would be consumed from doing so?"""
        pred = self.stmt[1]
        objVar: Node = self.stmt[2]
        boundOperands = []
        for op in self.operands:
            if isinstance(op, Variable):
                try:
                    op = inputBindings.binding[op]
                except KeyError:
                    return CandidateBinding(binding={}), self.operandsStmts

            boundOperands.append(op)

        if pred == MATH['sum']:
            obj = Literal(sum(map(numericNode, boundOperands)))
            if not isinstance(objVar, Variable):
                raise TypeError(f'expected Variable, got {objVar!r}')
            res = CandidateBinding({objVar: obj})
        elif pred == ROOM['asFarenheit']:
            if len(boundOperands) != 1:
                raise ValueError(":asFarenheit takes 1 subject operand")
            f = Literal(Decimal(numericNode(boundOperands[0])) * 9 / 5 + 32)
            if not isinstance(objVar, Variable):
                raise TypeError(f'expected Variable, got {objVar!r}')
            res = CandidateBinding({objVar: f})
        elif pred == MATH['greaterThan']:
            if not (numericNode(boundOperands[0]) > numericNode(boundOperands[1])):
                raise EvaluationFailed()
            res= CandidateBinding({})
        else:
            raise NotImplementedError(repr(pred))

        return res, self.operandsStmts


def numericNode(n: Node):
    if not isinstance(n, Literal):
        raise TypeError(f'expected Literal, got {n=}')
    val = n.toPython()
    if not isinstance(val, (int, float, Decimal)):
        raise TypeError(f'expected number, got {val=}')
    return val


def _parseList(graph, subj) -> Tuple[List[Node], Set[Triple]]:
    """"Do like Collection(g, subj) but also return all the 
    triples that are involved in the list"""
    out = []
    used = set()
    cur = subj
    while cur != RDF.nil:
        out.append(graph.value(cur, RDF.first))
        used.add((cur, RDF.first, out[-1]))

        next = graph.value(cur, RDF.rest)
        used.add((cur, RDF.rest, next))

        cur = next
    return out, used
