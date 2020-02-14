import json
import logging
import urllib

from rdflib import URIRef, Namespace, RDF, Literal
from twisted.internet import reactor
import treq

from httpputoutputs import HttpPutOutputs
from inputgraph import InputGraph

log = logging.getLogger('output')

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")
REASONING = Namespace("http://projects.bigasterisk.com/ns/reasoning/")

def secsFromLiteral(v):
    if v[-1] != 's':
        raise NotImplementedError(v)
    return float(v[:-1])

def ntStatement(stmt):
    def compact(u):
        if isinstance(u, URIRef) and u.startswith(ROOM):
            return 'room:' + u[len(ROOM):]
        return u.n3()
    return '%s %s %s .' % (compact(stmt[0]), compact(stmt[1]), compact(stmt[2]))


class Actions(object):
    def __init__(self, inputGraph: InputGraph, sendToLiveClients, mockOutput=False):
        self.inputGraph = inputGraph
        self.mockOutput = mockOutput
        self.putOutputs = HttpPutOutputs(mockOutput=mockOutput)
        self.sendToLiveClients = sendToLiveClients

    def putResults(self, inferred):
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
        deviceGraph = self.inputGraph.getGraph()
        activated = set()  # (subj,pred) pairs for which we're currently putting some value
        activated.update(self._putDevices(deviceGraph, inferred))
        self._oneShotPostActions(deviceGraph, inferred)
        self.putDefaults(deviceGraph, activated)

    def _putDevices(self, deviceGraph, inferred):
        activated = set()
        agentFor = {}
        for stmt in inferred:
            if stmt[1] == ROOM['putAgent']:
                agentFor[stmt[0]] = stmt[2]
        for stmt in inferred:
            log.debug('inferred stmt we might PUT: %s', ntStatement(stmt))
            putUrl = deviceGraph.value(stmt[0], ROOM['putUrl'])
            putPred = deviceGraph.value(stmt[0], ROOM['putPredicate'])
            matchPred = deviceGraph.value(stmt[0], ROOM['matchPredicate'],
                                          default=putPred)
            if putUrl and matchPred == stmt[1]:
                log.debug('putDevices: stmt %s leads to putting at %s',
                          ntStatement(stmt), putUrl.n3())
                self._put(putUrl + '?' + urllib.parse.urlencode([
                    ('s', str(stmt[0])),
                    ('p', str(putPred))]),
                          str(stmt[2].toPython()),
                          agent=agentFor.get(stmt[0], None),
                          refreshSecs=self._getRefreshSecs(stmt[0]))
                activated.add((stmt[0],
                               # didn't test that this should be
                               # stmt[1] and not putPred
                               stmt[1]))
        return activated

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
                log.debug('defaultStmts %s', ntStatement((s, p, obj)))
        self._putDevices(deviceGraph, defaultStmts)

    def _getRefreshSecs(self, target):
        # should be able to map(secsFromLiteral) in here somehow and
        # remove the workaround in httpputoutputs.currentRefreshSecs
        return self.inputGraph.rxValue(target, ROOM['refreshPutValue'],
                                       default=Literal('30s'))#.map(secsFromLiteral)

    def _put(self, url, payload, refreshSecs, agent=None):
        if isinstance(payload, str):
            payload = payload.encode('utf8')
        assert isinstance(payload, bytes)
        self.putOutputs.put(url, payload, agent, refreshSecs)

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
