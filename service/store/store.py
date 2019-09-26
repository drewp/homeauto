"""
persistent store of rdf statements, meant for stmts from users.

API is not typical rdf: putting statments replaces existing (s,o)
matches so there can be only one object at a time. Putting the special
object :unset clears the statement.
"""

import sys, logging
from docopt import docopt
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from rdfdb.patch import Patch
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.parser import StringInputSource
from twisted.internet import reactor
from twisted.python.filepath import FilePath
import cyclone.web
from standardservice.logsetup import log, verboseLogging

ROOM = Namespace('http://projects.bigasterisk.com/room/')

CTX = ROOM['stored']

class ValuesResource(cyclone.web.RequestHandler):
    def put(self):
        arg = self.request.arguments
        if arg.get('s') and arg.get('p'):
            self._onQueryStringStatement(arg['s'][-1], arg['p'][-1], self.request.body)
        else:
            self._onGraphBodyStatements(self.request.body, self.request.headers)
    post = put
    def _onQueryStringStatement(self, s, p, body):
        subj = URIRef(s)
        pred = URIRef(p)
        turtleLiteral = self.request.body
        try:
            obj = Literal(float(turtleLiteral))
        except ValueError:
            obj = Literal(turtleLiteral)
        self._onStatements([(subj, pred, obj)])

    def _onGraphBodyStatements(self, body, headers):
        # maybe quads only so we can track who made the input and from what interface?
        # Or your input of triples gets wrapped in a new quad in here?
        g = Graph()
        g.parse(StringInputSource(body), format='nt')
        if not g:
            raise ValueError("expected graph body")
        self._onStatements(list(g.triples((None, None, None))))

    def _onStatements(self, stmts):
        g = self.settings.masterGraph
        for s, p, o in stmts:
            patch = g.getObjectPatch(CTX, s, p, o)
            if o == ROOM['unset']:
                patch = Patch(delQuads=patch.delQuads)
            g.patch(patch)
        nquads = g.serialize(None, format='nquads')
        self.settings.dbFile.setContent(nquads)

if __name__ == '__main__':
    arg = docopt("""
    Usage: store.py [options]

    -v   Verbose
    """)
    verboseLogging(arg['-v'])

    masterGraph = PatchableGraph()
    dbFile = FilePath('/opt/homeauto_store/db.nquads')
    if dbFile.exists():
        masterGraph._graph.parse(dbFile.open(), format='nquads')

    port = 10015
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler,
         {"path": ".", "default_filename": "index.html"}),
        (r"/store", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/store/events", CycloneGraphEventsHandler,
         {'masterGraph': masterGraph}),
        (r'/values', ValuesResource),
    ], masterGraph=masterGraph, dbFile=dbFile, debug=arg['-v']),
                      interface='::')
    log.warn('serving on %s', port)

    reactor.run()
