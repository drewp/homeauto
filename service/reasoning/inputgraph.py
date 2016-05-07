import logging, time

from rdflib import Graph, ConjunctiveGraph
from rdflib import Namespace, URIRef, Literal, RDF
from rdflib.parser import StringInputSource

from twisted.python.filepath import FilePath
from twisted.internet.defer import inlineCallbacks, gatherResults

from rdflibtrig import addTrig
from graphop import graphEqual

log = logging.getLogger('fetch')

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")


def parseRdf(text, contentType):
    g = Graph()
    g.parse(StringInputSource(text), format={
        'text/n3': 'n3',
        }[contentType])
    return g


class InputGraph(object):
    def __init__(self, inputDirs, onChange, sourceSubstr=None):
        """
        this has one Graph that's made of:
          - all .n3 files from inputDirs (read at startup)
          - all the remote graphs, specified in the file graphs

        call updateFileData or updateRemoteData to reread those
        graphs. getGraph to access the combined graph.

        onChange(self) is called if the contents of the full graph
        change (in an interesting way) during updateFileData or
        updateRemoteData. Interesting means statements other than the
        ones with the predicates on the boring list. onChange(self,
        oneShot=True) means: don't store the result of this change
        anywhere; it needs to be processed only once

        sourceSubstr filters to only pull from sources containing the
        string (for debugging).
        """
        self.inputDirs = inputDirs
        self.onChange = onChange
        self.sourceSubstr = sourceSubstr
        self._fileGraph = Graph()
        self._remoteGraph = None
        self._combinedGraph = None
        self._oneShotAdditionGraph = None
        self._lastErrLog = {} # source: error

    def updateFileData(self):
        """
        make sure we contain the correct data from the files in inputDirs
        """
        # this sample one is actually only needed for the output, but I don't
        # think I want to have a separate graph for the output
        # handling
        log.debug("read file graphs")
        for fp in FilePath("input").walk():
            if fp.isdir():
                continue
            if fp.splitext()[1] != '.n3':
                continue
            log.debug("read %s", fp)
            # todo: if this fails, leave the report in the graph
            self._fileGraph.parse(fp.open(), format="n3")
            self._combinedGraph = None

        self.onChange(self)

    @inlineCallbacks
    def updateRemoteData(self):
        """
        read all remote graphs (which are themselves enumerated within
        the file data)
        """
        t1 = time.time()
        log.debug("read remote graphs")
        g = ConjunctiveGraph()

        @inlineCallbacks
        def fetchOne(source):
            try:
                fetchTime = yield addTrig(g, source, timeout=5)
            except Exception, e:
                e = str(e)
                if self._lastErrLog.get(source) != e:
                    log.error("  can't add source %s: %s", source, e)
                    self._lastErrLog[source] = e
                g.add((URIRef(source), ROOM['graphLoadError'], Literal(e)))
                g.add((URIRef(source), RDF.type, ROOM['FailedGraphLoad']))
            else:
                if self._lastErrLog.get(source):
                    log.warning("  source %s is back", source)
                    self._lastErrLog[source] = None
                g.add((URIRef(source), ROOM['graphLoadMs'],
                       Literal(round(fetchTime * 1000, 1))))

        fetchDone = []
        filtered = 0
        for source in self._fileGraph.objects(ROOM['reasoning'],
                                              ROOM['source']):
            if self.sourceSubstr and self.sourceSubstr not in source:
                filtered += 1
                continue
            fetchDone.append(fetchOne(source))
        yield gatherResults(fetchDone, consumeErrors=True)
        log.debug("loaded %s (skipping %s) in %.1f ms", len(fetchDone),
                  filtered, 1000 * (time.time() - t1))
        
        prevGraph = self._remoteGraph
        self._remoteGraph = g
        self._combinedGraph = None
        if (prevGraph is None or
            not graphEqual(g, prevGraph, ignorePredicates=[
                ROOM['signalStrength'],
                # perhaps anything with a number-datatype for its
                # object should be filtered out, and you have to make
                # an upstream quantization (e.g. 'temp high'/'temp
                # low') if you want to do reasoning on the difference
                URIRef("http://bigasterisk.com/map#lastSeenAgoSec"),
                URIRef("http://bigasterisk.com/map#lastSeenAgo"),
                ROOM['usingPower'],
                ROOM['idleTimeMinutes'],
                ROOM['idleTimeMs'],
                ROOM['graphLoadMs'],
                ROOM['localTimeToSecond'],
                ROOM['history'],
                ROOM['temperatureF'],
                ROOM['connectedAgo'],
                ])):
            log.debug("  remote graph changed")
            self.onChange(self)
        else:
            log.debug("  remote graph has no changes to trigger rules")

    def addOneShot(self, g):
        """
        add this graph to the total, call onChange, and then revert
        the addition of this graph
        """
        self._oneShotAdditionGraph = g
        self._combinedGraph = None
        try:
            self.onChange(self, oneShot=True, oneShotGraph=g)
        finally:
            self._oneShotAdditionGraph = None
            self._combinedGraph = None

    def addOneShotFromString(self, body, contentType):
        g = parseRdf(body, contentType)
        if not len(g):
            log.warn("incoming oneshot graph had no statements: %r", body)
            return 0
        t1 = time.time()
        self.addOneShot(g)
        return time.time() - t1
            
    def getGraph(self):
        """rdflib Graph with the file+remote contents of the input graph"""
        # this could be much faster with the combined readonly graph
        # view from rdflib
        if self._combinedGraph is None:
            self._combinedGraph = Graph()
            if self._fileGraph:
                for s in self._fileGraph:
                    self._combinedGraph.add(s)
            if self._remoteGraph:
                for s in self._remoteGraph:
                    self._combinedGraph.add(s)
            if self._oneShotAdditionGraph:
                for s in self._oneShotAdditionGraph:
                    self._combinedGraph.add(s)

        return self._combinedGraph
