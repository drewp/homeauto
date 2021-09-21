import unittest

from rdflib import RDF, ConjunctiveGraph, Literal, Namespace
from rdflib.parser import StringInputSource

EX = Namespace('http://example.com/')


def N3(txt: str):
    g = ConjunctiveGraph()
    prefix = """
@prefix : <http://example.com/> .
"""
    g.parse(StringInputSource((prefix + txt).encode('utf8')), format='n3')
    return g

