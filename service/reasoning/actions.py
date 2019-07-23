from rdflib import URIRef, Namespace, RDF, Literal
import logging
import urllib

from cyclone.httpclient import fetch
log = logging.getLogger('output')
log.setLevel(logging.WARN)

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")

class Actions(object):
    def __init__(self, sendToLiveClients):
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
        self._putDevices(deviceGraph, inferred)
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
                self._putInferred(deviceGraph, url, inferredObjects[0])
            elif len(inferredObjects) > 1:
                log.info("  conflict, ignoring: %s has %s of %s" %
                         (dev, pred, inferredObjects))
                # write about it to the inferred graph?
        
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
        log.info("_oneShotPostActions")
        def err(e):
            log.warn("post %s failed", postTarget)
        for osp in deviceGraph.subjects(RDF.type, ROOM['OneShotPost']):
            s = deviceGraph.value(osp, ROOM['subject'])
            p = deviceGraph.value(osp, ROOM['predicate'])
            if s is None or p is None:
                continue
            #log.info("checking for %s %s", s, p)
            for postTarget in inferred.objects(s, p):
                log.info("post target %r", postTarget)
                # this packet ought to have 'oneShot' in it somewhere
                self.sendToLiveClients({"s":s, "p":p, "o":postTarget})

                log.info("    POST %s", postTarget)
                fetch(postTarget, method="POST", timeout=2).addErrback(err)

    def _putDevices(self, deviceGraph, inferred):
        agentFor = {}
        for stmt in inferred:
            if stmt[1] == ROOM['putAgent']:
                agentFor[stmt[0]] = stmt[2]
        for stmt in inferred:
            log.info('inferred stmt we might PUT: %s', stmt)
            putUrl = deviceGraph.value(stmt[0], ROOM['putUrl'])
            putPred = deviceGraph.value(stmt[0], ROOM['putPredicate'])
            matchPred = deviceGraph.value(stmt[0], ROOM['matchPredicate'],
                                          default=putPred)
            if putUrl and matchPred == stmt[1]:
                log.info('putDevices: stmt %r %r %r leds to putting at %r',
                         stmt[0], stmt[1], stmt[2], putUrl)
                self._put(putUrl + '?' + urllib.urlencode([
                    ('s', str(stmt[0])),
                    ('p', str(putPred))]),
                          str(stmt[2].toPython()),
                          agent=agentFor.get(stmt[0], None))

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
            log.info("    put zero (%r) to %s", value.toPython(), putUrl)
            self._put(putUrl, payload=str(value))
            # this should be written back into the inferred graph
            # for feedback

    def _put(self, url, payload, agent=None):
        assert isinstance(payload, bytes)
        def err(e):
            log.warn("    put %s failed (%r)", url, e)
        log.info("    PUT %s payload=%s agent=%s", url, payload, agent)
        headers = {}
        if agent is not None:
            headers['x-foaf-agent'] = [str(agent)]
        fetch(url, method="PUT", postdata=payload, timeout=2,
              headers=headers).addErrback(err)
