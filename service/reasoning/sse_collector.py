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
from rdflib import ConjunctiveGraph
from rdflib.parser import StringInputSource
from docopt import docopt

from twisted_sse_demo.eventsource import EventSource

sys.path.append("../../lib")
from logsetup import log
from patchablegraph import jsonFromPatch, PatchableGraph, patchFromJson

sys.path.append("/my/proj/light9")
from light9.rdfdb.patch import Patch

class PatchSource(object):
    """wrap EventSource so it emits Patch objects and has an explicit stop method."""
    def __init__(self, url):
        self.url = url
        self._listeners = set()
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
            log.error(traceback.format_exc())
            raise
            
    def _onMessage(self, message):
        try:
            p = patchFromJson(message)
            self._sendPatch(p)
        except:
            log.error(traceback.format_exc())
            raise

    def _sendPatch(self, p):
        log.debug('PatchSource received patch %s', p.shortSummary())
        for lis in self._listeners:
            lis(p)
        
    def addPatchListener(self, func):
        self._listeners.add(func)

    def stop(self):
        log.info('stop read from %s', self.url)
        try:
            self._eventSource.protocol.stopProducing() #?
        except AttributeError:
            pass
        self._eventSource = None

    def __del__(self):
        if self._eventSource:
            raise ValueError

class GraphClient(object):
    """A listener of some PatchSources that emits patches to a cyclone SSEHandler."""

    def __init__(self, handler):
        self.handler = handler

        # The graph that the requester knows.
        # 
        # Note that often, 2 requests for the same streamId would have
        # the same graph contents in this attribute and ought to share
        # it. But, that's a little harder to write, and if clients
        # want different throttling rates or have stalled different
        # amounts, their currentGraph contents might drift apart
        # temporarily.
        self._currentGraph = PatchableGraph()
        self._currentGraph.addObserver(self._sendPatch)

    def addPatchSource(self, ps):
        """Connect this object to a PatchSource whose patches should get applied to our output graph"""
        # this is never getting released, so we'll keep sending until
        # no one wants the source anymore.
        ps.addPatchListener(self._onPatch)

    def _onPatch(self, p):
        self._currentGraph.patch(p)
        
    def _sendPatch(self, jsonPatch):
        self.handler.sendEvent(message=jsonPatch, event='patch')
    
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
        self.statements = collections.defaultdict(lambda: (set(), set())) # (s,p,o,c): (sourceUrls, handlers)`
        
    def addSseHandler(self, handler, streamId):
        log.info('addSseHandler %r %r', handler, streamId)
        matches = [s for s in config['streams'] if s['id'] == streamId]
        if len(matches) != 1:
            raise ValueError("%s matches for %r" % (len(matches), streamId))

        self.handlers.add(handler)
        for source in matches[0]['sources']:
            if source not in self.clients:
                ps = self.clients[source] = PatchSource(source)
                ps.addPatchListener(lambda p, source=source: self._onPatch(source, p))
            self.listeners.setdefault(source, []).append(handler)
        self._sendUpdatePatch(handler)

    def _onPatch(self, source, p):

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
            
    def _sendUpdatePatch(self, handler):
        """send a patch event out this handler to bring it up to date with self.statements"""
        adds = []
        dels = []
        statementsToClear = []
        for stmt, (sources, handlers) in self.statements.iteritems():
            if sources and (handler not in handlers):
                adds.append(stmt)
                handlers.add(handler)
            if not sources and (handler in handlers):
                dels.append(stmt)
                handlers.remove(handler)
                statementsToClear.append(stmt)
        # todo: cleanup statementsToClear
        p = Patch(addQuads=adds, delQuads=dels)
        if not p.isNoop():
            log.debug("send patch %s to %s", p.shortSummary(), handler)
            handler.sendEvent(message=jsonFromPatch(p), event='patch')
        
    def removeSseHandler(self, handler):
        log.info('removeSseHandler %r', handler)
        for url, handlers in self.listeners.items():
            keep = []
            for h in handlers:
                if h != handler:
                    keep.append(h)
            handlers[:] = keep
            if not keep:
                self.clients[url].stop()
                del self.clients[url]
                del self.listeners[url]
        self.handlers.remove(handler)
    
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
