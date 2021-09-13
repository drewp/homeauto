import logging
from decimal import Decimal
from typing import List, Set, Tuple

from prometheus_client import Summary
from rdflib import RDF, Literal, Namespace, URIRef
from rdflib.term import Node

from inference_types import Triple

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
