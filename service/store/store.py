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

ROOM = Namespace('http://projects.bigasterisk.com/room/')

logging.basicConfig()
log = logging.getLogger()

CTX = ROOM['stored']

class OutputPage(cyclone.web.RequestHandler):
    def put(self):
        arg = self.request.arguments
        if arg.get('s') and arg.get('p'):
            self._onQueryStringStatement(arg['s'][-1], arg['p'][-1], self.request.body)
        else:
            self._onGraphBodyStatements(self.request.body, self.request.headers)
            
    def _onQueryStringStatement(self, s, p, body):
        subj = URIRef(arg['s'][-1])
        pred = URIRef(arg['p'][-1])
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
    log.setLevel(logging.WARN)
    if arg['-v']:
        from twisted.python import log as twlog
        twlog.startLogging(sys.stdout)
        log.setLevel(logging.DEBUG)

    masterGraph = PatchableGraph()
    dbFile = FilePath('/opt/homeauto_store/db.nquads')
    if dbFile.exists():
        masterGraph._graph.parse(dbFile.open(), format='nquads')
    
    port = 10014
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler,
         {"path": ".", "default_filename": "index.html"}),
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler,
         {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
    ], masterGraph=masterGraph, dbFile=dbFile, debug=arg['-v']),
                      interface='::')
    log.warn('serving on %s', port)

    reactor.run()
