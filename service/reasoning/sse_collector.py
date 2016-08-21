"""
requesting /graph/foo returns an SSE patch stream that's the
result of fetching multiple other SSE patch streams. The result stream
may include new statements injected by this service.

Future:
- filter out unneeded stmts from the sources
- give a time resolution and concatenate any patches that come faster than that res
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

import sys, logging, traceback, json, collections
from twisted.internet import reactor
import cyclone.web, cyclone.sse
from rdflib import ConjunctiveGraph, URIRef, Namespace
from rdflib.parser import StringInputSource
from docopt import docopt

from twisted_sse_demo.eventsource import EventSource

sys.path.append("../../lib")
from logsetup import log
from patchablegraph import jsonFromPatch, PatchableGraph, patchFromJson

sys.path.append("/my/proj/light9")
from light9.rdfdb.patch import Patch

ROOM = Namespace("http://projects.bigasterisk.com/room/")
COLLECTOR = URIRef('http://bigasterisk.com/sse_collector/')

class ConnectionLost(object):
    pass

class PatchSource(object):
    """wrap EventSource so it emits Patch objects and has an explicit stop method."""
    def __init__(self, url):
        self.url = url
        self._listeners = set()
        log.info('start read from %s', url)
        self._eventSource = EventSource(url.toPython().encode('utf8'))
        self._eventSource.protocol.delimiter = '\n'

        self._eventSource.addEventListener('fullGraph', self._onFullGraph)
        self._eventSource.addEventListener('patch', self._onMessage)

    def _onFullGraph(self, message):
        try:
            g = ConjunctiveGraph()
            g.parse(StringInputSource(message), format='json-ld')
            p = Patch(addGraph=g)
            self._sendPatch(p, fullGraph=True)
        except:
            log.error(traceback.format_exc())
            raise
            
    def _onMessage(self, message):
        try:
            p = patchFromJson(message)
            self._sendPatch(p, fullGraph=False)
        except:
            log.error(traceback.format_exc())
            raise

    def _sendPatch(self, p, fullGraph):
        log.debug('PatchSource received patch %s', p.shortSummary())
        for lis in self._listeners:
            lis(p, fullGraph=fullGraph)
        
    def addPatchListener(self, func):
        """
        func(patch or ConnectionLost, fullGraph=[true if the patch is the initial fullgraph])
        """
        self._listeners.add(func)

    def stop(self):
        log.info('stop read from %s', self.url)
        try:
            self._eventSource.protocol.stopProducing() # needed?
        except AttributeError:
            pass
        self._eventSource = None

    def __del__(self):
        if self._eventSource:
            raise ValueError

class LocalStatements(object):
    def __init__(self, applyPatch):
        self.applyPatch = applyPatch
        self._sourceState = {} # source: state URIRef
        
    def setSourceState(self, source, state):
        """
        add a patch to the COLLECTOR graph about the state of this
        source. state=None to remove the source.
        """
        oldState = self._sourceState.get(source, None)
        if state == oldState:
            return
        log.info('source state %s -> %s', source, state)
        if oldState is None:
            self._sourceState[source] = state
            self.applyPatch(COLLECTOR, Patch(addQuads=[
                (COLLECTOR, ROOM['source'], source, COLLECTOR),
                (source, ROOM['state'], state, COLLECTOR),
            ]))
        elif state is None:
            del self._sourceState[source]
            self.applyPatch(COLLECTOR, Patch(delQuads=[
                (COLLECTOR, ROOM['source'], source, COLLECTOR),
                (source, ROOM['state'], oldState, COLLECTOR),
            ]))
        else:
            self._sourceState[source] = state
            self.applyPatch(COLLECTOR, Patch(
                addQuads=[
                (source, ROOM['state'], state, COLLECTOR),
                ],
                delQuads=[
                    (source, ROOM['state'], oldState, COLLECTOR),
                ]))
            
class GraphClients(object):
    """
    All the active GraphClient objects

    To handle all the overlapping-statement cases, we store a set of
    true statements along with the sources that are currently
    asserting them and the requesters who currently know them. As
    statements come and go, we make patches to send to requesters.
    
    todo: reconnect patchsources that go down and deal with their graph diffs
    """
    def __init__(self):
        self.clients = {}  # url: PatchSource
        self.handlers = set()  # handler
        self.listeners = {}  # url: [handler]  (handler may appear under multiple urls)

        # This table holds statements asserted by any of our sources
        # plus local statements that we introduce (source is
        # http://bigasterisk.com/sse_collector/).
        self.statements = collections.defaultdict(lambda: (set(), set())) # (s,p,o,c): (sourceUrls, handlers)`

        self._localStatements = LocalStatements(self._onPatch)

    def _pprintTable(self):
        for i, (stmt, (sources, handlers)) in enumerate(sorted(self.statements.items())):
            print "%03d. (%s, %s, %s, %s) from %s to %s" % (
                i,
                stmt[0].n3(),
                stmt[1].n3(),
                stmt[2].n3(),
                stmt[3].n3(),
                ','.join(s.n3() for s in sources),
                handlers)        
            
    def _sendUpdatePatch(self, handler):
        """send a patch event out this handler to bring it up to date with self.statements"""
        p = self._makeSyncPatch(handler)
        if not p.isNoop():
            log.debug("send patch %s to %s", p.shortSummary(), handler)
            handler.sendEvent(message=jsonFromPatch(p), event='patch')

    def _makeSyncPatch(self, handler):
        # todo: this could run all handlers at once, which is how we use it anyway
        adds = []
        dels = []
        statementsToClear = []
        for stmt, (sources, handlers) in self.statements.iteritems():
            relevantToHandler = handler in sum((self.listeners.get(s, []) for s in sources), [])
            handlerHasIt = handler in handlers
            if relevantToHandler and not handlerHasIt:
                adds.append(stmt)
                handlers.add(handler)
            elif not relevantToHandler and handlerHasIt:
                dels.append(stmt)
                handlers.remove(handler)
                if not handlers:
                    statementsToClear.append(stmt)
                    
        for stmt in statementsToClear:
            del self.statements[stmt]

        return Patch(addQuads=adds, delQuads=dels)
        
    def _onPatch(self, source, p, fullGraph=False):
        for stmt in p.addQuads:
            sourceUrls, handlers = self.statements[stmt]
            if source in sourceUrls:
                raise ValueError("%s added stmt that it already had: %s" % (source, stmt))
            sourceUrls.add(source)
        for stmt in p.delQuads:
            sourceUrls, handlers = self.statements[stmt]
            if source not in sourceUrls:
                raise ValueError("%s deleting stmt that it didn't have: %s" % (source, stmt))
            sourceUrls.remove(source)

        for h in self.handlers:
            self._sendUpdatePatch(h)

        if log.isEnabledFor(logging.DEBUG):
            self._pprintTable()

        if source != COLLECTOR:
            if fullGraph:
                self._localStatements.setSourceState(source, ROOM['fullGraphReceived'])
            else:
                self._localStatements.setSourceState(source, ROOM['patchesReceived'])
        
    def addSseHandler(self, handler, streamId):
        log.info('addSseHandler %r %r', handler, streamId)
        matches = [s for s in config['streams'] if s['id'] == streamId]
        if len(matches) != 1:
            raise ValueError("%s matches for %r" % (len(matches), streamId))

        self.handlers.add(handler)
        for source in map(URIRef, matches[0]['sources']):
            if source not in self.clients:
                self._localStatements.setSourceState(source, ROOM['connect'])
                ps = self.clients[source] = PatchSource(source)
                ps.addPatchListener(
                    lambda p, fullGraph, source=source: self._onPatch(source, p, fullGraph))
            self.listeners.setdefault(source, []).append(handler)
        self._sendUpdatePatch(handler)
        
    def removeSseHandler(self, handler):
        log.info('removeSseHandler %r', handler)
        
        statementsToClear = []
        for stmt, (sources, handlers) in self.statements.iteritems():
            handlers.discard(handler)
            if not sources and not handlers:
                statementsToClear.append(stmt)
        for stmt in statementsToClear:
            del self.statements[stmt]
                
        for url, handlers in self.listeners.items():
            keep = []
            for h in handlers:
                if h != handler:
                    keep.append(h)
            handlers[:] = keep
            if not keep:
                self._stopClient(url)
        self.handlers.remove(handler)

    def _stopClient(self, url):
        self.clients[url].stop()

        for stmt, (sources, handlers) in self.statements.iteritems():
            sources.discard(url)
        
        self._localStatements.setSourceState(url, None)
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
        9072,
        cyclone.web.Application(
            handlers=[
                (r'/graph/(.*)', SomeGraph),
            ],
            graphClients=graphClients),
        interface='::')
    reactor.run()
