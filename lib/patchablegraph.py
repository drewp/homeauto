import sys, json
import cyclone.sse
sys.path.append("/my/proj/light9")
from light9.rdfdb.grapheditapi import GraphEditApi
from rdflib import ConjunctiveGraph
from light9.rdfdb.rdflibpatch import patchQuads
from rdflib_jsonld.serializer import from_rdf

def writeGraphResponse(req, graph, acceptHeader):
    if acceptHeader == 'application/nquads':
        req.set_header('Content-type', 'application/nquads')
        graph.serialize(req, format='nquads')
    elif acceptHeader == 'application/ld+json':
        req.set_header('Content-type', 'application/ld+json')
        graph.serialize(req, format='json-ld', indent=2)
    else:
        req.set_header('Content-type', 'application/x-trig')
        graph.serialize(req, format='trig')

# forked from /my/proj/light9/light9/rdfdb/rdflibpatch.py
def graphFromQuads2(q):
    g = ConjunctiveGraph()
    #g.addN(q) # no effect on nquad output
    for s,p,o,c in q:
        g.get_context(c).add((s,p,o)) # kind of works with broken rdflib nquad serializer code
        #g.store.add((s,p,o), c) # no effect on nquad output
    return g

def patchAsJson(p):
    return json.dumps({'patch': {
        'adds': from_rdf(graphFromQuads2(p.addQuads)),
        'deletes': from_rdf(graphFromQuads2(p.delQuads)),
    }})

class PatchableGraph(GraphEditApi):
    """
    Master graph that you modify with self.patch, and we get the
    updates to all current listeners.
    """
    def __init__(self):
        self._graph = ConjunctiveGraph()
        self._observers = []

    def serialize(self, to, **kw):
        return self._graph.serialize(to, **kw)
        
    def patch(self, p):
        if p.isNoop():
            return
        patchQuads(self._graph,
                   deleteQuads=p.delQuads,
                   addQuads=p.addQuads,
                   perfect=False) # true?
        for ob in self._observers:
            ob(patchAsJson(p))

    def addObserver(self, onPatch):
        self._observers.append(onPatch)
        
    def removeObserver(self, onPatch):
        try:
            self._observers.remove(onPatch)
        except ValueError:
            pass
        

        
class GraphEventsHandler(cyclone.sse.SSEHandler):
    """
    One session with one client.
    
    returns current graph plus future patches to keep remote version
    in sync with ours.

    intsead of turning off buffering all over, it may work for this
    response to send 'x-accel-buffering: no', per
    http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering
    """
    def bind(self):
        mg = self.settings.masterGraph
        # todo: needs to be on one line, or else fix cyclone to stripe headers
        self.sendEvent(message=mg.serialize(None, format='json-ld', indent=None), event='fullGraph')
        mg.addObserver(self.onPatch)

    def onPatch(self, patchJson):
        self.sendEvent(message=patchJson, event='patch')
               
    def unbind(self):
        self.settings.masterGraph.removeObserver(self.onPatch)

