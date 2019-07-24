from rdflib import URIRef, Namespace, RDF, Literal
from twisted.internet import reactor
import logging
import urllib
import json
import time

import treq
log = logging.getLogger('output')

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")
REASONING = Namespace("http://projects.bigasterisk.com/ns/reasoning/")

class HttpPutOutput(object):
    def __init__(self, url, mockOutput=False):
        self.url = url
        self.mockOutput = mockOutput
        self.payload = None
        self.foafAgent = None
        self.nextCall = None
        self.lastErr = None
        self.numRequests = 0

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

    def setPayload(self, payload, foafAgent):
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
        log.debug("PUT %s payload=%s agent=%s", self.url, self.payload, self.foafAgent)
        if not self.mockOutput:
            self.currentRequest = treq.put(self.url, data=self.payload, headers=h, timeout=3)
            self.currentRequest.addCallback(self.onResponse).addErrback(self.onError)
        else:
            reactor.callLater(.2, self.onResponse, None)

        self.numRequests += 1

    def onResponse(self, resp):
        log.debug("  PUT %s ok", self.url)
        self.lastErr = None
        self.currentRequest = None
        self.nextCall = reactor.callLater(30, self.makeRequest)

    def onError(self, err):
        self.lastErr = err
        log.debug('  PUT %s failed: %s', self.url, err)
        self.currentRequest = None
        self.nextCall = reactor.callLater(50, self.makeRequest)

class HttpPutOutputs(object):
    """these grow forever"""
    def __init__(self, mockOutput=False):
        self.mockOutput = mockOutput
        self.state = {} # url: HttpPutOutput

    def put(self, url, payload, foafAgent):
        if url not in self.state:
            self.state[url] = HttpPutOutput(url, mockOutput=self.mockOutput)
        self.state[url].setPayload(payload, foafAgent)

class Actions(object):
    def __init__(self, sendToLiveClients, mockOutput=False):
        self.mockOutput = mockOutput
        self.putOutputs = HttpPutOutputs(mockOutput=mockOutput)
        self.sendToLiveClients = sendToLiveClients

    def putResults(self, deviceGraph, inferred):
        """
        some conclusions in the inferred graph lead to PUT requests
        getting made

        if the graph contains (?d ?p ?o) and ?d and ?p are a device
        and predicate we support PUTs for, then we look up
        (?d :putUrl ?url) and (?o :putValue ?val) and call
        PUT ?url <- ?val

        If the graph doesn't contain any matches, we use (?d
        :zeroValue ?val) for the value and PUT that.
        """
        activated = set()  # (subj,pred) pairs for which we're currently putting some value
        activated.update(self._putDevices(deviceGraph, inferred))
        self._oneShotPostActions(deviceGraph, inferred)
        for dev, pred in [
                #(URIRef('http://bigasterisk.com/host/bang/monitor'), ROOM.powerState),
                (URIRef('http://bigasterisk.com/host/dash/monitor'), ROOM.powerState),
                (URIRef('http://bigasterisk.com/host/frontdoor/monitor'), ROOM.powerState),
                (ROOM['storageCeilingLedLong'], ROOM.brightness),
                (ROOM['storageCeilingLedCross'], ROOM.brightness),
                (ROOM['garageOverhead'], ROOM.brightness),
                (ROOM['headboardWhite'], ROOM.brightness),
                (ROOM['changingWhite'], ROOM.brightness),
                (ROOM['starTrekLight'], ROOM.brightness),
                (ROOM['kitchenLight'], ROOM.brightness),
                (ROOM['kitchenCounterLight'], ROOM.brightness),
                (ROOM['livingRoomLamp1'], ROOM.brightness),
                (ROOM['livingRoomLamp2'], ROOM.brightness),
                (ROOM['loftDeskStrip'], ROOM.x),
                (ROOM['bedLedStrip'], ROOM.color),
            ]:
            url = deviceGraph.value(dev, ROOM.putUrl)

            log.debug('inferredObjects of dev=%s pred=%s',
                      deviceGraph.qname(dev),
                      deviceGraph.qname(pred))
            inferredObjects = list(inferred.objects(dev, pred))
            if len(inferredObjects) == 0:
                # rm this- use activated instead
                self._putZero(deviceGraph, dev, pred, url)
            elif len(inferredObjects) == 1:
                log.debug('  inferredObject: %s %s %r',
                          deviceGraph.qname(dev),
                          deviceGraph.qname(pred),
                          inferredObjects[0].toPython())
                activated.add((dev, pred))
                self._putInferred(deviceGraph, url, inferredObjects[0])
            elif len(inferredObjects) > 1:
                log.info("  conflict, ignoring: %s has %s of %s" %
                         (dev, pred, inferredObjects))
                # write about it to the inferred graph?
        self.putDefaults(deviceGraph, activated)

    def putDefaults(self, deviceGraph, activated):
        """
        If inferring (:a :b :c) would cause a PUT, you can say

        reasoning:defaultOutput reasoning:default [
          :subject :a
          :predicate :b
          :defaultObject :c
        ]

        and we'll do that PUT if no rule has put anything else with
        (:a :b *).
        """

        defaultStmts = set()
        for defaultDesc in deviceGraph.objects(REASONING['defaultOutput'],
                                               REASONING['default']):
            s = deviceGraph.value(defaultDesc, ROOM['subject'])
            p = deviceGraph.value(defaultDesc, ROOM['predicate'])
            if (s, p) not in activated:
                obj = deviceGraph.value(defaultDesc, ROOM['defaultObject'])

                defaultStmts.add((s, p, obj))
                log.debug('defaultStmts %s %s %s', s, p, obj)
        self._putDevices(deviceGraph, defaultStmts)

    def _oneShotPostActions(self, deviceGraph, inferred):
        """
        Inferred graph may contain some one-shot statements. We'll send
        statement objects to anyone on web sockets, and also generate
        POST requests as described in the graph.

        one-shot statement ?s ?p ?o
        with this in the graph:
          ?osp a :OneShotPost
          ?osp :subject ?s
          ?osp :predicate ?p
        this will cause a post to ?o
        """
        # nothing in this actually makes them one-shot yet. they'll
        # just fire as often as we get in here, which is not desirable
        log.debug("_oneShotPostActions")
        def err(e):
            log.warn("post %s failed", postTarget)
        for osp in deviceGraph.subjects(RDF.type, ROOM['OneShotPost']):
            s = deviceGraph.value(osp, ROOM['subject'])
            p = deviceGraph.value(osp, ROOM['predicate'])
            if s is None or p is None:
                continue
            #log.info("checking for %s %s", s, p)
            for postTarget in inferred.objects(s, p):
                log.debug("post target %r", postTarget)
                # this packet ought to have 'oneShot' in it somewhere
                self.sendToLiveClients({"s":s, "p":p, "o":postTarget})

                log.debug("    POST %s", postTarget)
                if not self.mockOutput:
                    treq.post(postTarget, timeout=2).addErrback(err)

    def _putDevices(self, deviceGraph, inferred):
        activated = set()
        agentFor = {}
        for stmt in inferred:
            if stmt[1] == ROOM['putAgent']:
                agentFor[stmt[0]] = stmt[2]
        for stmt in inferred:
            log.debug('inferred stmt we might PUT: %s', stmt)
            putUrl = deviceGraph.value(stmt[0], ROOM['putUrl'])
            putPred = deviceGraph.value(stmt[0], ROOM['putPredicate'])
            matchPred = deviceGraph.value(stmt[0], ROOM['matchPredicate'],
                                          default=putPred)
            if putUrl and matchPred == stmt[1]:
                log.debug('putDevices: stmt %r %r %r leds to putting at %r',
                         stmt[0], stmt[1], stmt[2], putUrl)
                self._put(putUrl + '?' + urllib.urlencode([
                    ('s', str(stmt[0])),
                    ('p', str(putPred))]),
                          str(stmt[2].toPython()),
                          agent=agentFor.get(stmt[0], None))
                activated.add((stmt[0],
                               # didn't test that this should be
                               # stmt[1] and not putPred
                               stmt[1]))
        return activated

    def _putInferred(self, deviceGraph, putUrl, obj):
        """
        HTTP PUT to putUrl, with a payload that's either obj's :putValue
        or obj itself.
        """
        value = deviceGraph.value(obj, ROOM.putValue)
        if value is not None:
            self._put(putUrl, payload=str(value))
        elif isinstance(obj, Literal):
            self._put(putUrl, payload=str(obj))
        else:
            log.warn("    don't know what payload to put for %s. obj=%r",
                        putUrl, obj)

    def _putZero(self, deviceGraph, dev, pred, putUrl):
        # zerovalue should be a function of pred as well.
        value = deviceGraph.value(dev, ROOM.zeroValue)
        if value is not None:
            log.debug("    put zero (%r) to %s", value.toPython(), putUrl)
            self._put(putUrl, payload=str(value))
            # this should be written back into the inferred graph
            # for feedback

    def _put(self, url, payload, agent=None):
        assert isinstance(payload, bytes)
        self.putOutputs.put(url, payload, agent)

import cyclone.sse

class PutOutputsTable(cyclone.sse.SSEHandler):
    def __init__(self, application, request):
        cyclone.sse.SSEHandler.__init__(self, application, request)
        self.actions = self.settings.reasoning.actions

    def bind(self, *args, **kwargs):
        self.bound = True
        self.loop()

    def unbind(self):
        self.bound = False

    def loop(self):
        if not self.bound:
            return

        self.sendEvent(message=json.dumps({
            'puts': [row.report() for _, row in
                     sorted(self.actions.putOutputs.state.items())],
        }), event='update')
        reactor.callLater(1, self.loop)
