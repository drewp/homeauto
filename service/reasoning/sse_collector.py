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
# should be from :reasoning :source ?s
'http://garage:9059/graph/events', # "garage pi"
'http://kitchen:9059/graph/events', # "kitchen pi"
'http://living:9059/graph/events', # "living room pi"
'http://slash:9059/graph/events', # "slash arduino"
'http://bed:9059/graph/events', # "bed pi"
'http://brace6:9059/graph/events', # "brace arduino"
'http://changing:9059/graph/events', # "changing pi"
'http://bang:9075/graph/events', # "env"
'http://bang:9070/graph/events', # "wifi usage"
'http://bang:9099/graph/events', # "trails"
'http://dash:9095/graph/events', # "dash monitor"
'http://dash:9107/graph/events', # "dash x idle"
'http://brace6:9095/graph/events', # "brace monitor"
'http://brace6:9107/graph/events', # "brace x idle"
'http://slash:9095/graph/events', # "slash monitor"
'http://slash:9107/graph/events', # "slash x idle" 



         ]
     },
    ]
}

from crochet import no_setup
no_setup()

import sys, logging, collections
from twisted.internet import reactor
import cyclone.web, cyclone.sse
from rdflib import URIRef, Namespace
from docopt import docopt


sys.path.append("../../lib")
from logsetup import log
from patchablegraph import jsonFromPatch

sys.path.append("/my/proj/light9")
from light9.rdfdb.patch import Patch

from patchsource import ReconnectingPatchSource

ROOM = Namespace("http://projects.bigasterisk.com/room/")
COLLECTOR = URIRef('http://bigasterisk.com/sse_collector/')

class LocalStatements(object):
    """
    functions that make statements originating from sse_collector itself
    """
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

def abbrevTerm(t):
    if isinstance(t, URIRef):
        return (t.replace('http://projects.bigasterisk.com/room/', 'room:')
                .replace('http://bigasterisk.com/sse_collector/', 'sc:'))
    return t

def abbrevStmt(stmt):
    return '(%s %s %s %s)' % tuple(map(abbrevTerm, stmt))
    
class ActiveStatements(object):
    def __init__(self):

        # This table holds statements asserted by any of our sources
        # plus local statements that we introduce (source is
        # http://bigasterisk.com/sse_collector/).
        self.statements = collections.defaultdict(lambda: (set(), set())) # (s,p,o,c): (sourceUrls, handlers)`
    
    def _postDeleteStatements(self):
        statements = self.statements
        class PostDeleter(object):
            def __enter__(self):
                self._garbage = []
                return self
            def add(self, stmt):
                self._garbage.append(stmt)
            def __exit__(self, type, value, traceback):
                if type is not None:
                    raise
                for stmt in self._garbage:
                    del statements[stmt]
        return PostDeleter()
        
    def pprintTable(self):
        for i, (stmt, (sources, handlers)) in enumerate(sorted(self.statements.items())):
            print "%03d. %-80s from %s to %s" % (
                i, abbrevStmt(stmt), [abbrevTerm(s) for s in sources], handlers)        

    def makeSyncPatch(self, handler, sources):
        # todo: this could run all handlers at once, which is how we use it anyway
        adds = []
        dels = []
        
        with self._postDeleteStatements() as garbage:
            for stmt, (stmtSources, handlers) in self.statements.iteritems():
                belongsInHandler = not set(sources).isdisjoint(stmtSources)
                handlerHasIt = handler in handlers
                #log.debug("%s %s %s", abbrevStmt(stmt), belongsInHandler, handlerHasIt)
                if belongsInHandler and not handlerHasIt:
                    adds.append(stmt)
                    handlers.add(handler)
                elif not belongsInHandler and handlerHasIt:
                    dels.append(stmt)
                    handlers.remove(handler)
                    if not handlers and not stmtSources:
                        garbage.add(stmt)

        return Patch(addQuads=adds, delQuads=dels)
        
    def applySourcePatch(self, source, p):
        for stmt in p.addQuads:
            sourceUrls, handlers = self.statements[stmt]
            if source in sourceUrls:
                raise ValueError("%s added stmt that it already had: %s" %
                                 (source, abbrevStmt(stmt)))
            sourceUrls.add(source)
            
        with self._postDeleteStatements() as garbage:
            for stmt in p.delQuads:
                sourceUrls, handlers = self.statements[stmt]
                if source not in sourceUrls:
                    raise ValueError("%s deleting stmt that it didn't have: %s" %
                                     (source, abbrevStmt(stmt)))
                sourceUrls.remove(source)
                # this is rare, since some handler probably still has
                # the stmt we're deleting, but it can happen e.g. when
                # a handler was just deleted
                if not sourceUrls and not handlers:
                    garbage.add(stmt)

    def replaceSourceStatements(self, source, stmts):
        log.debug('replaceSourceStatements with %s stmts', len(stmts))
        newStmts = set(stmts)

        with self._postDeleteStatements() as garbage:
            for stmt, (sources, handlers) in self.statements.iteritems():
                if source in sources:
                    if stmt not in stmts:
                        sources.remove(source)
                        if not sources and not handlers:
                            garbage.add(stmt)
                else:
                    if stmt in stmts:
                        sources.add(source)
                newStmts.discard(stmt)

        self.applySourcePatch(source, Patch(addQuads=newStmts, delQuads=[]))

    def discardHandler(self, handler):
        with self._postDeleteStatements() as garbage:
            for stmt, (sources, handlers) in self.statements.iteritems():
                handlers.discard(handler)
                if not sources and not handlers:
                    garbage.add(stmt)

    def discardSource(self, source):
        with self._postDeleteStatements() as garbage:
            for stmt, (sources, handlers) in self.statements.iteritems():
                sources.discard(source)
                if not sources and not handlers:
                    garbage.add(stmt)
                    
class GraphClients(object):
    """
    All the active PatchSources and SSEHandlers

    To handle all the overlapping-statement cases, we store a set of
    true statements along with the sources that are currently
    asserting them and the requesters who currently know them. As
    statements come and go, we make patches to send to requesters.
    """
    def __init__(self):
        self.clients = {}  # url: PatchSource (COLLECTOR is not listed)
        self.handlers = set()  # handler
        self.statements = ActiveStatements()
        
        self._localStatements = LocalStatements(self._onPatch)

    def _sourcesForHandler(self, handler):
        streamId = handler.streamId
        matches = [s for s in config['streams'] if s['id'] == streamId]
        if len(matches) != 1:
            raise ValueError("%s matches for %r" % (len(matches), streamId))
        return map(URIRef, matches[0]['sources']) + [COLLECTOR]
        
    def _onPatch(self, source, p, fullGraph=False):
        if fullGraph:
            # a reconnect may need to resend the full graph even
            # though we've already sent some statements
            self.statements.replaceSourceStatements(source, p.addQuads)
        else:
            self.statements.applySourcePatch(source, p)

        self._sendUpdatePatch()

        if log.isEnabledFor(logging.DEBUG):
            self.statements.pprintTable()

        if source != COLLECTOR:
            self._localStatements.setSourceState(
                source,
                ROOM['fullGraphReceived'] if fullGraph else
                ROOM['patchesReceived'])

    def _sendUpdatePatch(self, handler=None):
        """
        send a patch event out this handler to bring it up to date with
        self.statements
        """
        # reduce loops here- prepare all patches at once
        for h in (self.handlers if handler is None else [handler]):
            p = self.statements.makeSyncPatch(h, self._sourcesForHandler(h))
            if not p.isNoop():
                log.debug("send patch %s to %s", p.shortSummary(), h)
                h.sendEvent(message=jsonFromPatch(p), event='patch')
        
    def addSseHandler(self, handler):
        log.info('addSseHandler %r %r', handler, handler.streamId)
        self.handlers.add(handler)
        
        for source in self._sourcesForHandler(handler):
            if source not in self.clients and source != COLLECTOR:
                self._localStatements.setSourceState(source, ROOM['connect'])
                self.clients[source] = ReconnectingPatchSource(
                    source, listener=lambda p, fullGraph, source=source: self._onPatch(
                        source, p, fullGraph))
        self._sendUpdatePatch(handler)
        
    def removeSseHandler(self, handler):
        log.info('removeSseHandler %r', handler)

        self.statements.discardHandler(handler)

        for source in self._sourcesForHandler(handler):
            for otherHandler in self.handlers:
                if (otherHandler != handler and
                    source in self._sourcesForHandler(otherHandler)):
                    break
            else:
                self._stopClient(source)
            
        self.handlers.remove(handler)

    def _stopClient(self, url):
        if url == COLLECTOR:
            return
            
        self.clients[url].stop()

        self.statements.discardSource(url)
        
        self._localStatements.setSourceState(url, None)
        del self.clients[url]
        

class SomeGraph(cyclone.sse.SSEHandler):
    _handlerSerial = 0
    def __init__(self, application, request):
        cyclone.sse.SSEHandler.__init__(self, application, request)
        self.streamId = request.uri[len('/graph/'):]
        self.graphClients = self.settings.graphClients
        
        self._serial = SomeGraph._handlerSerial
        SomeGraph._handlerSerial += 1

    def __repr__(self):
        return '<Handler #%s>' % self._serial
        
    def bind(self):
        self.graphClients.addSseHandler(self)
        
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
