"""
see how a browser talks to this PatchableGraph
"""

from rdflib import Namespace, Literal, ConjunctiveGraph, URIRef, RDF
from twisted.internet import reactor
import cyclone.web

from standardservice.logsetup import log, verboseLogging
from patchablegraph import PatchableGraph, CycloneGraphEventsHandler, CycloneGraphHandler

verboseLogging(True)

graph = PatchableGraph()
g = ConjunctiveGraph()
g.add((URIRef('http://example.com/s'),
       URIRef('http://example.com/p'),
       URIRef('http://example.com/o'),
       URIRef('http://example.com/g')))
graph.setToGraph(g)

class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r'/graph', CycloneGraphHandler, {'masterGraph': graph}),
            (r'/graph/events', CycloneGraphEventsHandler,
             {'masterGraph': graph}),
        ]
        cyclone.web.Application.__init__(self, handlers)


reactor.listenTCP(8021, Application())
reactor.run()
