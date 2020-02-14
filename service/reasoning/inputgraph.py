import logging, time
import weakref
from typing import Callable

from greplin import scales
from rdflib import Graph, ConjunctiveGraph
from rdflib import Namespace, URIRef, RDFS
from rdflib.parser import StringInputSource
from rx.subjects import BehaviorSubject
from twisted.python.filepath import FilePath
from twisted.internet import reactor

from patchablegraph.patchsource import ReconnectingPatchSource
from rdfdb.rdflibpatch import patchQuads
from rdfdb.patch import Patch

log = logging.getLogger('fetch')

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")


STATS = scales.collection('/web',
                          scales.PmfStat('combineGraph'),
)


def parseRdf(text: str, contentType: str):
    g = Graph()
    g.parse(StringInputSource(text), format={
        'text/n3': 'n3',
        }[contentType])
    return g


class RemoteData(object):
    def __init__(self, onChange: Callable[[], None]):
        """we won't fire onChange during init"""
        self.onChange = onChange
        self.graph = ConjunctiveGraph()
        reactor.callLater(0, self._finishInit)

    def _finishInit(self):
        self.patchSource = ReconnectingPatchSource(
            URIRef('http://bang:9072/graph/home'),
            #URIRef('http://frontdoor:10012/graph/events'),
            self.onPatch, reconnectSecs=10, agent='reasoning')

    def onPatch(self, p: Patch, fullGraph: bool):
        if fullGraph:
            self.graph = ConjunctiveGraph()
        patchQuads(self.graph,
                   deleteQuads=p.delQuads,
                   addQuads=p.addQuads,
                   perfect=True)

        ignorePredicates = [
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
            ROOM['connectedAgo'],
            RDFS['comment'],
        ]
        ignoreContexts = [
            URIRef('http://bigasterisk.com/sse_collector/'),
            ]
        for affected in p.addQuads + p.delQuads:
            if (affected[1] not in ignorePredicates and
                affected[3] not in ignoreContexts):
                log.debug("  remote graph changed")
                self.onChange()
                break
        else:
            log.debug("  remote graph has no changes to trigger rules")


class InputGraph(object):
    def __init__(self, inputDirs, onChange):
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
        """
        self.inputDirs = inputDirs
        self._onChange = onChange
        self._fileGraph = Graph()
        self._remoteData = RemoteData(lambda: self.onChangeLocal())
        self._combinedGraph = None
        self._oneShotAdditionGraph = None
        self._rxValues = weakref.WeakKeyDictionary()

    def onChangeLocal(self, oneShot=False, oneShotGraph=None):
        self._combinedGraph = None
        self._onChange(self, oneShot=oneShot, oneShotGraph=oneShotGraph)
        for rxv, (subj, pred, default) in self._rxValues.items():
            self._rxUpdate(subj, pred, default, rxv)

    def _rxUpdate(self, subj, pred, default, rxv):
        rxv.on_next(self.getGraph().value(subj, pred, default=default))

    def rxValue(self, subj, pred, default):# -> BehaviorSubject:
        value = BehaviorSubject(default)
        self._rxValues[value] = (subj, pred, default)
        self._rxUpdate(subj, pred, default, value)
        return value

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

        self.onChangeLocal()

    def addOneShot(self, g):
        """
        add this graph to the total, call onChange, and then revert
        the addition of this graph
        """
        self._oneShotAdditionGraph = g
        self._combinedGraph = None
        try:
            self.onChangeLocal(oneShot=True, oneShotGraph=g)
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

    @STATS.combineGraph.time()
    def getGraph(self):
        """rdflib Graph with the file+remote contents of the input graph"""
        # this could be much faster with the combined readonly graph
        # view from rdflib
        if self._combinedGraph is None:
            self._combinedGraph = Graph()
            if self._fileGraph:
                for s in self._fileGraph:
                    self._combinedGraph.add(s)
            for s in self._remoteData.graph:
                self._combinedGraph.add(s)
            if self._oneShotAdditionGraph:
                for s in self._oneShotAdditionGraph:
                    self._combinedGraph.add(s)

        return self._combinedGraph
