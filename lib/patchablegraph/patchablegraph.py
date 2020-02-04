"""
Design:

1. Services each have (named) graphs, which they patch as things
   change. PatchableGraph is an object for holding this graph.
2. You can http GET that graph, or ...
3. You can http GET/SSE that graph and hear about modifications to it
4. The client that got the graph holds and maintains a copy. The
   client may merge together multiple graphs.
5. Client queries its graph with low-level APIs or client-side sparql.
6. When the graph changes, the client knows and can update itself at
   low or high granularity.


See also:
* http://iswc2007.semanticweb.org/papers/533.pdf RDFSync: efficient remote synchronization of RDF
models
* https://www.w3.org/2009/12/rdf-ws/papers/ws07 Supporting Change Propagation in RDF
* https://www.w3.org/DesignIssues/lncs04/Diff.pdf Delta: an ontology for the distribution of
differences between RDF graphs

"""
import json, logging, itertools

from greplin import scales
from rdfdb.grapheditapi import GraphEditApi
from rdflib import ConjunctiveGraph
from rdflib.parser import StringInputSource
from rdflib_jsonld.serializer import from_rdf
import cyclone.sse

from cycloneerr import PrettyErrorHandler
from rdfdb.patch import Patch
from rdfdb.rdflibpatch import patchQuads, inGraph

log = logging.getLogger('patchablegraph')

def _writeGraphForBrowser(req, graph):
    # We think this is a browser, so respond with a live graph view
    # (todo)
    req.set_header('Content-type', 'text/plain')
    lines = graph.serialize(None, format='nquads').splitlines()
    lines.sort()
    req.write(b'\n'.join(lines))


def _writeGraphResponse(req, graph, acceptHeader: str):
    if acceptHeader == 'application/nquads':
        req.set_header('Content-type', 'application/nquads')
        graph.serialize(req, format='nquads')
    elif acceptHeader == 'application/ld+json':
        req.set_header('Content-type', 'application/ld+json')
        graph.serialize(req, format='json-ld', indent=2)
    else:
        if acceptHeader.startswith('text/html'):
            _writeGraphForBrowser(req, graph)
            return
        req.set_header('Content-type', 'application/x-trig')
        graph.serialize(req, format='trig')

# forked from /my/proj/light9/light9/rdfdb/rdflibpatch.py
def _graphFromQuads2(q):
    g = ConjunctiveGraph()
    #g.addN(q) # no effect on nquad output
    for s,p,o,c in q:
        g.get_context(c).add((s,p,o)) # kind of works with broken rdflib nquad serializer code
        #g.store.add((s,p,o), c) # no effect on nquad output
    return g

def jsonFromPatch(p):
    return json.dumps({'patch': {
        'adds': from_rdf(_graphFromQuads2(p.addQuads)),
        'deletes': from_rdf(_graphFromQuads2(p.delQuads)),
    }})
patchAsJson = jsonFromPatch # deprecated name


def patchFromJson(j):
    body = json.loads(j)['patch']
    a = ConjunctiveGraph()
    a.parse(StringInputSource(json.dumps(body['adds']).encode('utf8')), format='json-ld')
    d = ConjunctiveGraph()
    d.parse(StringInputSource(json.dumps(body['deletes']).encode('utf8')), format='json-ld')
    return Patch(addGraph=a, delGraph=d)

def graphAsJson(g):
    # This is not the same as g.serialize(format='json-ld')! That
    # version omits literal datatypes.
    return json.dumps(from_rdf(g))

_graphsInProcess = itertools.count()
class PatchableGraph(GraphEditApi):
    """
    Master graph that you modify with self.patch, and we get the
    updates to all current listeners.
    """
    def __init__(self):
        self._graph = ConjunctiveGraph()
        self._observers = []
        scales.init(self, '/patchableGraph%s' % next(_graphsInProcess))

    _serialize = scales.PmfStat('serialize')
    def serialize(self, *arg, **kw):
        with self._serialize.time():
            return self._graph.serialize(*arg, **kw)

    _patch = scales.PmfStat('patch')
    _len = scales.IntStat('statementCount')
    def patch(self, p):
        with self._patch.time():
            # assuming no stmt is both in p.addQuads and p.delQuads.
            dels = set([q for q in p.delQuads if inGraph(q, self._graph)])
            adds = set([q for q in p.addQuads if not inGraph(q, self._graph)])
            minimizedP = Patch(addQuads=adds, delQuads=dels)
            if minimizedP.isNoop():
                return
            patchQuads(self._graph,
                       deleteQuads=dels,
                       addQuads=adds,
                       perfect=False) # true?
            for ob in self._observers:
                ob(patchAsJson(p))
            self._len = len(self._graph)

    def asJsonLd(self):
        return graphAsJson(self._graph)

    _currentObservers = scales.IntStat('observers/current')
    _observersAdded = scales.IntStat('observers/added')
    def addObserver(self, onPatch):
        self._observers.append(onPatch)
        self._currentObservers = len(self._observers)
        self._observersAdded += 1

    def removeObserver(self, onPatch):
        try:
            self._observers.remove(onPatch)
        except ValueError:
            pass
        self._currentObservers = len(self._observers)

    def setToGraph(self, newGraph):
        self.patch(Patch.fromDiff(self._graph, newGraph))

    _sendSimpleGraph = scales.PmfStat('serve/simpleGraph')
    _sendFullGraph = scales.PmfStat('serve/events/sendFull')
    _sendPatch = scales.PmfStat('serve/events/sendPatch')

class CycloneGraphHandler(PrettyErrorHandler, cyclone.web.RequestHandler):
    def initialize(self, masterGraph):
        self.masterGraph = masterGraph

    def get(self):
        with self.masterGraph._sendSimpleGraph.time():
            _writeGraphResponse(self, self.masterGraph,
                                self.request.headers.get('accept', ''))


class CycloneGraphEventsHandler(cyclone.sse.SSEHandler):
    """
    One session with one client.

    returns current graph plus future patches to keep remote version
    in sync with ours.

    intsead of turning off buffering all over, it may work for this
    response to send 'x-accel-buffering: no', per
    http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering
    """
    def __init__(self, application, request, masterGraph):
        cyclone.sse.SSEHandler.__init__(self, application, request)
        self.masterGraph = masterGraph

    def bind(self):
        with self.masterGraph._sendFullGraph.time():
            graphJson = self.masterGraph.asJsonLd()
            log.debug("send fullGraph event: %s", graphJson)
            self.sendEvent(message=graphJson, event=b'fullGraph')
            self.masterGraph.addObserver(self.onPatch)

    def onPatch(self, patchJson):
        with self.masterGraph._sendPatch.time():
            # throttle and combine patches here- ideally we could see how
            # long the latency to the client is to make a better rate choice
            self.sendEvent(message=patchJson, event=b'patch')

    def unbind(self):
        self.masterGraph.removeObserver(self.onPatch)
