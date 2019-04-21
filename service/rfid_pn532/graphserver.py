import sys, datetime, cyclone.web, json
from twisted.internet import reactor, task
from rdflib import Namespace, Literal, ConjunctiveGraph
import rdflib_jsonld.parser
from patchablegraph import PatchableGraph, CycloneGraphEventsHandler, CycloneGraphHandler

class CurrentGraph(cyclone.web.RequestHandler):
    def put(self):
        g = ConjunctiveGraph()
        rdflib_jsonld.parser.to_rdf(json.loads(self.request.body), g)
        self.settings.masterGraph.setToGraph(g)

def main():
    from twisted.python import log as twlog
    twlog.startLogging(sys.stderr)
    masterGraph = PatchableGraph()

    class Application(cyclone.web.Application):
        def __init__(self):
            handlers = [
                (r"/()", cyclone.web.StaticFileHandler,
                 {"path": ".", "default_filename": "index.html"}),
                (r'/graph', CycloneGraphHandler, {'masterGraph': masterGraph}),   
                (r'/graph/events', CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
                (r'/currentGraph', CurrentGraph),
            ]
            cyclone.web.Application.__init__(self, handlers,
                                             masterGraph=masterGraph)

    reactor.listenTCP(10012, Application())
    reactor.run()

if __name__ == '__main__':
    main()
