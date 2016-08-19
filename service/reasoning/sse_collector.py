"""
requesting /graph/foo returns an SSE patch stream that's the
result of fetching multiple other SSE patch streams. The result stream
may include new statements injected by this service.

Future:
- filter out unneeded stmts from the sources
- give a time resolution and concatenate patches faster than that res
"""

config = {
    'streams': [
        {'id': 'home',
         'sources': [
             #'http://bang:9059/graph/events',
             'http://plus:9075/graph/events',     
         ]
     },
    ]
}

from crochet import no_setup
no_setup()

import sys, logging, weakref, traceback, json
from twisted.internet import reactor
import cyclone.web, cyclone.sse
from rdflib import ConjunctiveGraph
from rdflib.parser import StringInputSource
from docopt import docopt

from twisted_sse_demo.eventsource import EventSource

sys.path.append("../../lib")
from logsetup import log
from patchablegraph import patchAsJson

sys.path.append("/my/proj/light9")
from light9.rdfdb.patch import Patch

def patchFromJson(j):
    body = json.loads(j)['patch']
    a = ConjunctiveGraph()
    a.parse(StringInputSource(json.dumps(body['adds'])), format='json-ld')
    d = ConjunctiveGraph()
    d.parse(StringInputSource(json.dumps(body['deletes'])), format='json-ld')
    return Patch(addGraph=a, delGraph=d)

class PatchSource(object):
    """wrap EventSource so it emits Patch objects and has an explicit stop method"""
    def __init__(self, url):
        self.url = url
        self._listeners = set()#weakref.WeakSet()
        log.info('start read from %s', url)
        self._eventSource = EventSource(url)
        self._eventSource.protocol.delimiter = '\n'

        self._eventSource.addEventListener('fullGraph', self._onFullGraph)
        self._eventSource.addEventListener('patch', self._onMessage)

    def _onFullGraph(self, message):
        try:
            g = ConjunctiveGraph()
            g.parse(StringInputSource(message), format='json-ld')
            p = Patch(addGraph=g)
            self._sendPatch(p)
        except:
            traceback.print_exc()
            
    def _onMessage(self, message):
        try:
            p = patchFromJson(message)
            self._sendPatch(p)
        except:
            traceback.print_exc()

    def _sendPatch(self, p):
        log.info('output patch to %s listeners', p, len(self._listeners))
        for lis in self._listeners:
            lis(p)
        
    def addPatchListener(self, func):
        self._listeners.add(func)

    def stop(self):
        log.info('stop read from %s', self.url)
        self._eventSource.protocol.stopProducing() #?
        self._eventSource = None

    def __del__(self):
        if self._eventSource:
            raise ValueError

class GraphClient(object):
    """A listener of some EventSources that sends patches to one of our clients."""

    def __init__(self, handler, patchSources):
        self.handler = handler

        for ps in patchSources:
            ps.addPatchListener(self.onPatch)

    def onPatch(self, p):
        self.handler.sendEvent(message=patchAsJson(p), event='patch')
    
class GraphClients(object):
    """All the active EventClient objects"""
    def __init__(self):
        self.clients = {}  # url: EventClient
        self.listeners = {}  # url: [GraphClient]

    def addSseHandler(self, handler, streamId):
        log.info('addSseHandler %r %r', handler, streamId)
        matches = [s for s in config['streams'] if s['id'] == streamId]
        if len(matches) != 1:
            raise ValueError("%s matches for %r" % (len(matches), streamId))
        ecs = []
        for source in matches[0]['sources']:
            if source not in self.clients:
                self.clients[source] = PatchSource(source)
            ecs.append(self.clients[source])
            
        self.listeners.setdefault(source, []).append(GraphClient(handler, ecs))
        print self.__dict__
        
    def removeSseHandler(self, handler):
        log.info('removeSseHandler %r', handler)
        for url, graphClients in self.listeners.items():
            keep = []
            for gc in graphClients:
                if gc.handler != handler:
                    keep.append(gc)
            graphClients[:] = keep
            if not keep:
                self.clients[url].stop()
                del self.clients[url]
                del self.listeners[url]
    
class SomeGraph(cyclone.sse.SSEHandler):
    def __init__(self, application, request):
        cyclone.sse.SSEHandler.__init__(self, application, request)
        self.id = request.uri[len('/graph/'):]
        self.graphClients = self.settings.graphClients
        
    def bind(self):
        self.graphClients.addSseHandler(self, self.id)
        
    def unbind(self):
        self.graphClients.removeSseHandler(self)

if __name__ == '__main__':

    arg = docopt("""
    Usage: sse_collector.py [options]

    -v   Verbose
    """)
    
    if arg['-v']:
        import twisted.python.log
        twisted.python.log.startLogging(sys.stdout)
        log.setLevel(logging.DEBUG)


    graphClients = GraphClients()
        
    reactor.listenTCP(
        9071,
        cyclone.web.Application(
            handlers=[
                (r'/graph/(.*)', SomeGraph),
            ],
            graphClients=graphClients),
        interface='::')
    reactor.run()
