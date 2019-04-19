# Stubs for rdflib (Python 3.4)
#
from typing import Tuple, Union


from rdflib.namespace import RDF, RDFS, OWL, XSD

# this is the 1st way that worked. 'from rdflib.term import URIRef' did not work.
import rdflib.namespace as _n
Namespace = _n.Namespace

import rdflib.term as _t
URIRef = _t.URIRef
Literal = _t.Literal
BNode = _t.BNode

import rdflib.graph as _g
ConjunctiveGraph = _g.ConjunctiveGraph
Graph = _g.Graph

# not part of rdflib
StatementType = Tuple[Union[URIRef, BNode], URIRef, _t.Node, URIRef]
