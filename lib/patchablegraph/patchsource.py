import logging
import traceback
from rdflib import ConjunctiveGraph
from rdflib.parser import StringInputSource
from twisted.internet import reactor, defer

from patchablegraph import patchFromJson
from rdfdb.patch import Patch
from twisted_sse_demo.eventsource import EventSource

log = logging.getLogger('fetch')

class PatchSource(object):
    """wrap EventSource so it emits Patch objects and has an explicit stop method."""
    def __init__(self, url, agent):
        self.url = str(url)

        # add callbacks to these to learn if we failed to connect
        # (approximately) or if the ccnnection was unexpectedly lost
        self.connectionFailed = defer.Deferred()
        self.connectionLost = defer.Deferred()
        
        self._listeners = set()
        log.info('start read from %s', url)
        # note: fullGraphReceived isn't guaranteed- the stream could
        # start with patches
        self._fullGraphReceived = False
        self._eventSource = EventSource(url.toPython().encode('utf8'),
                                        userAgent=agent)

        self._eventSource.addEventListener(b'fullGraph', self._onFullGraph)
        self._eventSource.addEventListener(b'patch', self._onPatch)
        self._eventSource.onerror(self._onError)
        self._eventSource.onConnectionLost = self._onDisconnect

    def state(self):
        return {
            'url': self.url,
            'fullGraphReceived': self._fullGraphReceived,
        }
        
    def addPatchListener(self, func):
        """
        func(patch, fullGraph=[true if the patch is the initial fullgraph])
        """
        self._listeners.add(func)

    def stop(self):
        log.info('stop read from %s', self.url)
        try:
            self._eventSource.protocol.stopProducing() # needed?
        except AttributeError:
            pass
        self._eventSource = None

    def _onDisconnect(self, reason):
        log.debug('PatchSource._onDisconnect from %s (%s)', self.url, reason)
        # skip this if we're doing a stop?
        self.connectionLost.callback(None)

    def _onError(self, msg):
        log.debug('PatchSource._onError from %s %r', self.url, msg)
        if not self._fullGraphReceived:
            self.connectionFailed.callback(msg)
        else:
            self.connectionLost.callback(msg)

    def _onFullGraph(self, message):
        try:
            g = ConjunctiveGraph()
            g.parse(StringInputSource(message), format='json-ld')
            p = Patch(addGraph=g)
            self._sendPatch(p, fullGraph=True)
        except Exception:
            log.error(traceback.format_exc())
            raise
        self._fullGraphReceived = True
            
    def _onPatch(self, message):
        try:
            p = patchFromJson(message)
            self._sendPatch(p, fullGraph=False)
        except:
            log.error(traceback.format_exc())
            raise

    def _sendPatch(self, p, fullGraph):
        log.debug('PatchSource %s received patch %s (fullGraph=%s)',
                  self.url, p.shortSummary(), fullGraph)
        for lis in self._listeners:
            lis(p, fullGraph=fullGraph)
        
    def __del__(self):
        if self._eventSource:
            raise ValueError("PatchSource wasn't stopped before del")

class ReconnectingPatchSource(object):
    """
    PatchSource api, but auto-reconnects internally and takes listener
    at init time to not miss any patches. You'll get another
    fullGraph=True patch if we have to reconnect.

    todo: generate connection stmts in here
    """
    def __init__(self, url, listener, reconnectSecs=60, agent='unset'):
        # type: (str, Any, Any, str)
        self.url = url
        self._stopped = False
        self._listener = listener
        self.reconnectSecs = reconnectSecs
        self.agent = agent
        self._reconnect()

    def _reconnect(self):
        if self._stopped:
            return
        self._ps = PatchSource(self.url, agent=self.agent)
        self._ps.addPatchListener(self._onPatch)
        self._ps.connectionFailed.addCallback(self._onConnectionFailed)
        self._ps.connectionLost.addCallback(self._onConnectionLost)        

    def _onPatch(self, p, fullGraph):
        self._listener(p, fullGraph=fullGraph)

    def state(self):
        return {
            'reconnectedPatchSource': self._ps.state(),
        }
        
    def stop(self):
        self._stopped = True
        self._ps.stop()
        
    def _onConnectionFailed(self, arg):
        reactor.callLater(self.reconnectSecs, self._reconnect)
        
    def _onConnectionLost(self, arg):
        reactor.callLater(self.reconnectSecs, self._reconnect)        
 
