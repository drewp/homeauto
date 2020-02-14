import logging
import time

from rdflib import URIRef
from rx.subjects import BehaviorSubject
from twisted.internet import reactor
from twisted.python.failure import Failure
from twisted.internet.interfaces import IDelayedCall
import treq
from typing import Optional

log = logging.getLogger('httpputoutputs')


class HttpPutOutput(object):
    lastChangeTime: float

    def __init__(self, url: str,
                 refreshSecs: BehaviorSubject,
                 mockOutput=False):
        self.url = url
        self.mockOutput = mockOutput
        self.payload: Optional[str] = None
        self.foafAgent: Optional[URIRef] = None
        self.nextCall: IDelayedCall = None
        self.lastErr: Optional[Failure] = None
        self.numRequests: int = 0
        self.refreshSecs: float = refreshSecs

    def report(self):
        return {
            'url': self.url,
            'urlAbbrev': self.url
            .replace('http%3A%2F%2Fprojects.bigasterisk.com%2Froom%2F', ':')
            .replace('http://projects.bigasterisk.com/room/', ':')
            .replace('.vpn-home.bigasterisk.com', '.vpn-home'),
            'payload': self.payload,
            'numRequests': self.numRequests,
            'lastChangeTime': round(self.lastChangeTime, 2),
            'lastErr': str(self.lastErr) if self.lastErr is not None else None,
            }

    def setPayload(self, payload: str, foafAgent: URIRef):
        if self.numRequests > 0 and (self.payload == payload and
                                     self.foafAgent == foafAgent):
            return
        self.payload = payload
        self.foafAgent = foafAgent
        self.lastChangeTime = time.time()
        self.makeRequest()

    def makeRequest(self):
        if self.payload is None:
            log.debug("PUT None to %s - waiting", self.url)
            return
        h = {}
        if self.foafAgent:
            h['x-foaf-agent'] = self.foafAgent
        if self.nextCall and self.nextCall.active():
            self.nextCall.cancel()
            self.nextCall = None
        self.lastErr = None
        log.debug("PUT %s payload=%s agent=%s",
                  self.url, self.payload, self.foafAgent)
        if not self.mockOutput:
            self.currentRequest = treq.put(self.url, data=self.payload.encode('utf8'),
                                           headers=h, timeout=3)
            self.currentRequest.addCallback(self.onResponse).addErrback(
                self.onError)
        else:
            reactor.callLater(.2, self.onResponse, None)

        self.numRequests += 1

    def currentRefreshSecs(self):
        out = None
        if 1:
            # workaround
            def secsFromLiteral(v):
                if v[-1] != 's':
                    raise NotImplementedError(v)
                return float(v[:-1])

            out = secsFromLiteral(self.refreshSecs.value)
        else:
            # goal: caller should map secsFromLiteral on the
            # observable, so we see a float
            def recv(v):
                log.info('recv %r', v)
            import ipdb;ipdb.set_trace()
            self.refreshSecs.subscribe(recv)
            if out is None:
                raise ValueError('refreshSecs had no value')
        log.debug('    got refresh %r', out)
        return out

    def onResponse(self, resp):
        log.debug("  PUT %s ok", self.url)
        self.lastErr = None
        self.currentRequest = None
        self.nextCall = reactor.callLater(self.currentRefreshSecs(),
                                          self.makeRequest)

    def onError(self, err):
        self.lastErr = err
        log.debug('  PUT %s failed: %s', self.url, err)
        self.currentRequest = None
        self.nextCall = reactor.callLater(self.currentRefreshSecs(),
                                          self.makeRequest)


class HttpPutOutputs(object):
    """these grow forever"""
    def __init__(self, mockOutput=False):
        self.mockOutput = mockOutput
        self.state = {} # url: HttpPutOutput

    def put(self, url: str, payload: str, foafAgent: str, refreshSecs: float):
        if url not in self.state:
            self.state[url] = HttpPutOutput(url, mockOutput=self.mockOutput,
                                            refreshSecs=refreshSecs)
        self.state[url].setPayload(payload, foafAgent)
