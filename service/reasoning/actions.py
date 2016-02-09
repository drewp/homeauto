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
        
        self._oneShotPostActions(deviceGraph, inferred)
        for dev, pred in [
                # the config of each putUrl should actually be in the
                # context of a dev and predicate pair, and then that would
                # be the source of this list
                #(DEV.theaterDoorLock, ROOM.state),
                #(URIRef('http://bigasterisk.com/host/bang/monitor'), ROOM.powerState),
                (URIRef('http://bigasterisk.com/host/dash/monitor'), ROOM.powerState),
                (URIRef('http://projects.bigasterisk.com/room/storageCeilingLedLong'), ROOM.brightness),
                (URIRef('http://projects.bigasterisk.com/room/storageCeilingLedCross'), ROOM.brightness),
                (URIRef('http://projects.bigasterisk.com/room/headboardWhite'), ROOM.brightness),
                (URIRef('http://projects.bigasterisk.com/room/bedLedStrip'), ROOM.color),
            ]:
            url = deviceGraph.value(dev, ROOM.putUrl)

            if url and dev == DEV.theaterDoorLock: # ew
                self._put(url+"/mode", payload="output")

            inferredObjects = list(inferred.objects(dev, pred))
            if len(inferredObjects) == 0:
                self._putZero(deviceGraph, dev, pred, url)
            elif len(inferredObjects) == 1:
                self._putInferred(deviceGraph, url, inferredObjects[0])
            elif len(inferredObjects) > 1:
                log.info("conflict, ignoring: %s has %s of %s" %
                         (dev, pred, inferredObjects))
                # write about it to the inferred graph?

        #self._frontDoorPuts(deviceGraph, inferred)

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
            for postTarget in inferred.objects(s, p):
                log.info("post target %r", postTarget)
                # this packet ought to have 'oneShot' in it somewhere
                self.sendToLiveClients({"s":s, "p":p, "o":postTarget})

                log.info("    POST %s", postTarget)
                fetch(postTarget, method="POST", timeout=2).addErrback(err)
        self._postMpdCommands(inferred)
        
    def _postMpdCommands(self, inferred):
        """special case to be eliminated. mpd play urls are made of an
        mpd service and a song/album/playlist uri to be played.
        Ideally the graph rules would assemble these like
        http://{mpd}/addAndPlay?uri={toPlay} or maybe toPlay as the payload
        which would be fairly general but still allow toPlay uris to
        be matched with any player."""

        rootSkippingAuth = "http://brace:9009/"
        for mpd in [URIRef("http://bigasterisk.com/host/brace/mpd")]:

            for song in inferred.objects(mpd, ROOM['startMusic']):
                log.info("mpd statement: %r" % song)
                assert song.startswith('http://bigasterisk.com/music/')
                self.post(rootSkippingAuth + "addAndPlay" + urllib.quote(song[len("http://bigasterisk.com/music"):]))

            for state in inferred.objects(mpd, ROOM['playState']):
                log.info('hello playstate %s', state)
                if state == ROOM['pause']:
                    log.info("mpd %s %s", mpd, state)
                    self.post(rootSkippingAuth + "mpd/pause")
            for vol in inferred.objects(mpd, ROOM['audioState']):
                if vol == ROOM['volumeStepUp']:
                    self.post(rootSkippingAuth + "volumeAdjust?amount=6&max=70")
                if vol == ROOM['volumeStepDown']:
                    self.post(rootSkippingAuth + "volumeAdjust?amount=-6&min=10")
            

    def _frontDoorPuts(self, deviceGraph, inferred):
        # todo: shouldn't have to be a special case
        brt = inferred.value(DEV.frontDoorLcd, ROOM.brightness)
        if brt is None:
            return
        url = deviceGraph.value(DEV.frontDoorLcdBrightness, ROOM.putUrl)
        log.info("put lcd %s brightness %s", url, brt)
        self._put(str(url) + "?brightness=%s" % str(brt), payload='')

        msg = "open %s motion %s" % (
            inferred.value(DEV['frontDoorOpenIndicator'], ROOM.text),
            inferred.value(DEV['frontDoorMotionIndicator'], ROOM.text))
        # this was meant to be 2 chars in the bottom row, but the
        # easier test was to replace the whole top msg
        #restkit.Resource("http://slash:9080/").put("lcd", message=msg)

    


    def _put(self, url, payload):
        def err(e):
            log.warn("    put %s failed (%r)", url, e)
        log.info("    PUT %s payload=%r", url, payload)
        fetch(url, method="PUT", postdata=payload, timeout=2).addErrback(err)
        
    def post(self, postTarget):
        log.info("special mpd POST %s", postTarget)
        def err(e):
            log.warn("post %s failed", postTarget)
        fetch(postTarget, method="POST", timeout=2).addErrback(err)
        
    def _putZero(self, deviceGraph, dev, pred, putUrl):
        # zerovalue should be a function of pred as well.
        value = deviceGraph.value(dev, ROOM.zeroValue)
        if value is not None:
            log.info("put zero (%r) to %s", value, putUrl)
            self._put(putUrl, payload=str(value))
            # this should be written back into the inferred graph
            # for feedback

    def _putInferred(self, deviceGraph, putUrl, obj):
        """
        HTTP PUT to putUrl, with a payload that's either obj's :putValue
        or obj itself.
        """
        value = deviceGraph.value(obj, ROOM.putValue)
        if value is not None:
            log.info("put %s to %s", value, putUrl)
            self._put(putUrl, payload=str(value))
        elif isinstance(obj, Literal):
            log.info("put %s to %s", obj, putUrl)
            self._put(putUrl, payload=str(obj))
        else:
            log.warn("don't know what payload to put for %s. obj=%r",
                        putUrl, obj)
