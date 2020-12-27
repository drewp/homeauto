"""
requesting /graph/foo returns an SSE patch stream that's the
result of fetching multiple other SSE patch streams. The result stream
may include new statements injected by this service.

Future:
- filter out unneeded stmts from the sources
- give a time resolution and concatenate any patches that come faster than that res
"""
import collections
import json
import logging
import time
from typing import (Any, Callable, Dict, List, NewType, Optional, Sequence, Set, Tuple, Union)

import cyclone.sse
import cyclone.web
from docopt import docopt
from patchablegraph import jsonFromPatch
from patchablegraph.patchsource import PatchSource, ReconnectingPatchSource
from prometheus_client import Counter, Gauge, Histogram, Summary
from prometheus_client.exposition import generate_latest
from prometheus_client.registry import REGISTRY
from rdfdb.patch import Patch
from rdflib import Namespace,  URIRef
from rdflib.term import Node, Statement
from standardservice.logsetup import enableTwistedLog, log
from twisted.internet import defer, reactor

from collector_config import config


#SourceUri = NewType('SourceUri', URIRef) # doesn't work
class SourceUri(URIRef):
    pass


ROOM = Namespace("http://projects.bigasterisk.com/room/")
COLLECTOR = SourceUri(URIRef('http://bigasterisk.com/sse_collector/'))

GET_STATE_CALLS = Summary("get_state_calls", 'calls')
LOCAL_STATEMENTS_PATCH_CALLS = Summary("local_statements_patch_calls", 'calls')
MAKE_SYNC_PATCH_CALLS = Summary("make_sync_patch_calls", 'calls')
ON_PATCH_CALLS = Summary("on_patch_calls", 'calls')
SEND_UPDATE_PATCH_CALLS = Summary("send_update_patch_calls", 'calls')
REPLACE_SOURCE_STATEMENTS_CALLS = Summary("replace_source_statements_calls", 'calls')


class Metrics(cyclone.web.RequestHandler):

    def get(self):
        self.add_header('content-type', 'text/plain')
        self.write(generate_latest(REGISTRY))


class LocalStatements(object):
    """
    functions that make statements originating from sse_collector itself
    """

    def __init__(self, applyPatch: Callable[[URIRef, Patch], None]):
        self.applyPatch = applyPatch
        self._sourceState: Dict[SourceUri, URIRef] = {}  # source: state URIRef

    @LOCAL_STATEMENTS_PATCH_CALLS.time()
    def setSourceState(self, source: SourceUri, state: URIRef):
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
            self.applyPatch(COLLECTOR, Patch(addQuads=[
                (source, ROOM['state'], state, COLLECTOR),
            ], delQuads=[
                (source, ROOM['state'], oldState, COLLECTOR),
            ]))


def abbrevTerm(t: Union[URIRef, Node]) -> Union[str, Node]:
    if isinstance(t, URIRef):
        return (t.replace('http://projects.bigasterisk.com/room/', 'room:').replace('http://projects.bigasterisk.com/device/',
                                                                                    'dev:').replace('http://bigasterisk.com/sse_collector/', 'sc:'))
    return t


def abbrevStmt(stmt: Statement) -> str:
    return '(%s %s %s %s)' % (abbrevTerm(stmt[0]), abbrevTerm(stmt[1]), abbrevTerm(stmt[2]), abbrevTerm(stmt[3]))


class PatchSink(cyclone.sse.SSEHandler):
    _handlerSerial = 0

    def __init__(self, application: cyclone.web.Application, request):
        cyclone.sse.SSEHandler.__init__(self, application, request)
        self.bound = False
        self.created = time.time()
        self.graphClients = self.settings.graphClients

        self._serial = PatchSink._handlerSerial
        PatchSink._handlerSerial += 1
        self.lastPatchSentTime: float = 0.0

    def __repr__(self) -> str:
        return '<Handler #%s>' % self._serial

    def state(self) -> Dict:
        return {
            'created': round(self.created, 2),
            'ageHours': round((time.time() - self.created) / 3600, 2),
            'streamId': self.streamId,
            'remoteIp': self.request.remote_ip,  # wrong, need some forwarded-for thing
            'foafAgent': self.request.headers.get('X-Foaf-Agent'),
            'userAgent': self.request.headers.get('user-agent'),
        }

    def bind(self, *args, **kwargs):
        self.streamId = args[0]

        self.graphClients.addSseHandler(self)
        # If something goes wrong with addSseHandler, I don't want to
        # try removeSseHandler.
        self.bound = True

    def unbind(self) -> None:
        if self.bound:
            self.graphClients.removeSseHandler(self)


StatementTable = Dict[Statement, Tuple[Set[SourceUri], Set[PatchSink]]]


class PostDeleter(object):

    def __init__(self, statements: StatementTable):
        self.statements = statements

    def __enter__(self):
        self._garbage: List[Statement] = []
        return self

    def add(self, stmt: Statement):
        self._garbage.append(stmt)

    def __exit__(self, type, value, traceback):
        if type is not None:
            raise NotImplementedError()
        for stmt in self._garbage:
            del self.statements[stmt]


class ActiveStatements(object):

    def __init__(self):
        # This table holds statements asserted by any of our sources
        # plus local statements that we introduce (source is
        # http://bigasterisk.com/sse_collector/).
        self.table: StatementTable = collections.defaultdict(lambda: (set(), set()))

    def state(self) -> Dict:
        return {
            'len': len(self.table),
        }

    def postDeleteStatements(self) -> PostDeleter:
        return PostDeleter(self.table)

    def pprintTable(self) -> None:
        for i, (stmt, (sources, handlers)) in enumerate(sorted(self.table.items())):
            print("%03d. %-80s from %s to %s" % (i, abbrevStmt(stmt), [abbrevTerm(s) for s in sources], handlers))

    @MAKE_SYNC_PATCH_CALLS.time()
    def makeSyncPatch(self, handler: PatchSink, sources: Set[SourceUri]):
        # todo: this could run all handlers at once, which is how we
        # use it anyway
        adds = []
        dels = []

        with self.postDeleteStatements() as garbage:
            for stmt, (stmtSources, handlers) in self.table.items():
                belongsInHandler = not sources.isdisjoint(stmtSources)
                handlerHasIt = handler in handlers
                # log.debug("%s belong=%s has=%s",
                #           abbrevStmt(stmt), belongsInHandler, handlerHasIt)
                if belongsInHandler and not handlerHasIt:
                    adds.append(stmt)
                    handlers.add(handler)
                elif not belongsInHandler and handlerHasIt:
                    dels.append(stmt)
                    handlers.remove(handler)
                    if not handlers and not stmtSources:
                        garbage.add(stmt)

        return Patch(addQuads=adds, delQuads=dels)

    def applySourcePatch(self, source: SourceUri, p: Patch):
        for stmt in p.addQuads:
            sourceUrls, handlers = self.table[stmt]
            if source in sourceUrls:
                raise ValueError("%s added stmt that it already had: %s" % (source, abbrevStmt(stmt)))
            sourceUrls.add(source)

        with self.postDeleteStatements() as garbage:
            for stmt in p.delQuads:
                sourceUrls, handlers = self.table[stmt]
                if source not in sourceUrls:
                    raise ValueError("%s deleting stmt that it didn't have: %s" % (source, abbrevStmt(stmt)))
                sourceUrls.remove(source)
                # this is rare, since some handler probably still has
                # the stmt we're deleting, but it can happen e.g. when
                # a handler was just deleted
                if not sourceUrls and not handlers:
                    garbage.add(stmt)

    @REPLACE_SOURCE_STATEMENTS_CALLS.time()
    def replaceSourceStatements(self, source: SourceUri, stmts: Sequence[Statement]):
        log.debug('replaceSourceStatements with %s stmts', len(stmts))
        newStmts = set(stmts)

        with self.postDeleteStatements() as garbage:
            for stmt, (sources, handlers) in self.table.items():
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

    def discardHandler(self, handler: PatchSink):
        with self.postDeleteStatements() as garbage:
            for stmt, (sources, handlers) in self.table.items():
                handlers.discard(handler)
                if not sources and not handlers:
                    garbage.add(stmt)

    def discardSource(self, source: SourceUri):
        with self.postDeleteStatements() as garbage:
            for stmt, (sources, handlers) in self.table.items():
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
        self.clients: Dict[SourceUri, PatchSource] = {}  # (COLLECTOR is not listed)
        self.handlers: Set[PatchSink] = set()
        self.statements: ActiveStatements = ActiveStatements()

        self._localStatements = LocalStatements(self._onPatch)

    def state(self) -> Dict:
        return {
            'clients': sorted([ps.state() for ps in self.clients.values()], key=lambda r: r['reconnectedPatchSource']['url']),
            'sseHandlers': sorted([h.state() for h in self.handlers], key=lambda r: (r['streamId'], r['created'])),
            'statements': self.statements.state(),
        }

    def _sourcesForHandler(self, handler: PatchSink) -> List[SourceUri]:
        streamId = handler.streamId
        matches = [s for s in config['streams'] if s['id'] == streamId]
        if len(matches) != 1:
            raise ValueError("%s matches for %r" % (len(matches), streamId))
        return [SourceUri(URIRef(s)) for s in matches[0]['sources']] + [COLLECTOR]

    @ON_PATCH_CALLS.time()
    def _onPatch(self, source: SourceUri, p: Patch, fullGraph: bool = False):
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
            self._localStatements.setSourceState(source, ROOM['fullGraphReceived'] if fullGraph else ROOM['patchesReceived'])

    @SEND_UPDATE_PATCH_CALLS.time()
    def _sendUpdatePatch(self, handler: Optional[PatchSink] = None):
        """
        send a patch event out this handler to bring it up to date with
        self.statements
        """
        now = time.time()
        selected = self.handlers
        if handler is not None:
            if handler not in self.handlers:
                log.error("called _sendUpdatePatch on a handler that's gone")
                return
            selected = {handler}
        # reduce loops here- prepare all patches at once
        for h in selected:
            period = .9
            if 'Raspbian' in h.request.headers.get('user-agent', ''):
                period = 5
            if h.lastPatchSentTime > now - period:
                continue
            p = self.statements.makeSyncPatch(h, set(self._sourcesForHandler(h)))
            log.debug('makeSyncPatch for %r: %r', h, p.jsonRepr)
            if not p.isNoop():
                log.debug("send patch %s to %s", p.shortSummary(), h)
                # This can be a giant line, which was a problem
                # once. Might be nice for this service to try to break
                # it up into multiple sends, although there's no
                # guarantee at all since any single stmt could be any
                # length.
                h.sendEvent(message=jsonFromPatch(p).encode('utf8'), event=b'patch')
                h.lastPatchSentTime = now
            else:
                log.debug('nothing to send to %s', h)

    def addSseHandler(self, handler: PatchSink):
        log.info('addSseHandler %r %r', handler, handler.streamId)

        # fail early if id doesn't match
        sources = self._sourcesForHandler(handler)

        self.handlers.add(handler)

        for source in sources:
            if source not in self.clients and source != COLLECTOR:
                log.debug('connect to patch source %s', source)
                self._localStatements.setSourceState(source, ROOM['connect'])
                self.clients[source] = ReconnectingPatchSource(source,
                                                               listener=lambda p, fullGraph, source=source: self._onPatch(source, p, fullGraph),
                                                               reconnectSecs=10)
        log.debug('bring new client up to date')

        self._sendUpdatePatch(handler)

    def removeSseHandler(self, handler: PatchSink):
        log.info('removeSseHandler %r', handler)
        self.statements.discardHandler(handler)
        for source in self._sourcesForHandler(handler):
            for otherHandler in self.handlers:
                if (otherHandler != handler and source in self._sourcesForHandler(otherHandler)):
                    # still in use
                    break
            else:
                self._stopClient(source)

        self.handlers.remove(handler)

    def _stopClient(self, url: SourceUri):
        if url == COLLECTOR:
            return

        self.clients[url].stop()

        self.statements.discardSource(url)

        self._localStatements.setSourceState(url, None)
        if url in self.clients:
            del self.clients[url]

        self.cleanup()

    def cleanup(self):
        """
        despite the attempts above, we still get useless rows in the table
        sometimes
        """
        with self.statements.postDeleteStatements() as garbage:
            for stmt, (sources, handlers) in self.statements.table.items():
                if not sources and not any(h in self.handlers for h in handlers):
                    garbage.add(stmt)


class State(cyclone.web.RequestHandler):

    @GET_STATE_CALLS.time()
    def get(self) -> None:
        try:
            state = self.settings.graphClients.state()
            self.write(json.dumps({'graphClients': state}, indent=2, default=lambda obj: '<unserializable>'))
        except Exception:
            import traceback
            traceback.print_exc()
            raise


class GraphList(cyclone.web.RequestHandler):

    def get(self) -> None:
        self.write(json.dumps(config['streams']))


if __name__ == '__main__':
    arg = docopt("""
    Usage: sse_collector.py [options]

    -v   Verbose
    -i  Info level only
    """)

    if arg['-v'] or arg['-i']:
        enableTwistedLog()
        log.setLevel(logging.DEBUG if arg['-v'] else logging.INFO)
        defer.setDebugging(True)

    graphClients = GraphClients()

    reactor.listenTCP(9072,
                      cyclone.web.Application(handlers=[
                          (r"/()", cyclone.web.StaticFileHandler, {
                              "path": ".",
                              "default_filename": "index.html"
                          }),
                          (r'/state', State),
                          (r'/graph/', GraphList),
                          (r'/graph/(.+)', PatchSink),
                          (r'/metrics', Metrics),
                      ],
                                              graphClients=graphClients),
                      interface='::')
    reactor.run()
