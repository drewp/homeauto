import unittest

from rdflib import RDF, ConjunctiveGraph, Literal, Namespace
from rdflib.parser import StringInputSource

from lhs_evaluation import _parseList

EX = Namespace('http://example.com/')


def N3(txt: str):
    g = ConjunctiveGraph()
    prefix = """
@prefix : <http://example.com/> .
"""
    g.parse(StringInputSource((prefix + txt).encode('utf8')), format='n3')
    return g


class TestParseList(unittest.TestCase):

    def test0Elements(self):
        g = N3(":a :b () .")
        bn = g.value(EX['a'], EX['b'])
        elems, used = _parseList(g, bn)
        self.assertEqual(elems, [])
        self.assertFalse(used)

    def test1Element(self):
        g = N3(":a :b (0) .")
        bn = g.value(EX['a'], EX['b'])
        elems, used = _parseList(g, bn)
        self.assertEqual(elems, [Literal(0)])
        used = sorted(used)
        self.assertEqual(used, [
            (bn, RDF.first, Literal(0)),
            (bn, RDF.rest, RDF.nil),
        ])
