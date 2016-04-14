#!bin/python
"""
Graph consists of:
  input/* (read at startup)
  webinput/* (new files are noticed in here)
  any number of remote graphs, specified in the other graph as objects of (:reasoning, :source, *), reread constantly

gather subgraphs from various services, run them through a rules
engine, and make http requests with the conclusions.

E.g. 'when drew's phone is near the house, and someone is awake,
unlock the door when the door's motion sensor is activated'

When do we gather? The services should be able to trigger us, perhaps
with PSHB, that their graph has changed.
"""


from twisted.internet import reactor, task
from twisted.internet.defer import inlineCallbacks, gatherResults
from twisted.python.filepath import FilePath
import time, traceback, sys, json, logging
from rdflib import Graph, ConjunctiveGraph
from rdflib import Namespace, URIRef, Literal, RDF
from rdflib.parser import StringInputSource

import cyclone.web, cyclone.websocket
from inference import infer
from rdflibtrig import addTrig
from graphop import graphEqual
from docopt import docopt
from actions import Actions
from FuXi.Rete.RuleStore import N3RuleStore

sys.path.append("../../lib")
from logsetup import log
log.setLevel(logging.WARN)
outlog = logging.getLogger('output')
outlog.setLevel(logging.WARN)

sys.path.append('../../../ffg/ffg')
import evtiming

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")


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

        
class Reasoning(object):
    def __init__(self):
        self.prevGraph = None
        self.lastPollTime = 0
        self.lastError = ""

        self.actions = Actions(sendToLiveClients)

        self.rulesN3 = "(not read yet)"
        self.inferred = Graph() # gets replaced in each graphChanged call

        self.inputGraph = InputGraph([], self.graphChanged)      
        self.inputGraph.updateFileData()

    @evtiming.serviceLevel.timed('readRules')
    def readRules(self):
        self.rulesN3 = open('rules.n3').read() # for web display
        self.ruleStore = N3RuleStore()
        self.ruleGraph = Graph(self.ruleStore)
        self.ruleGraph.parse('rules.n3', format='n3') # for inference

    @inlineCallbacks
    def poll(self):
        t1 = time.time()
        try:
            yield self.inputGraph.updateRemoteData()
            self.lastPollTime = time.time()
        except Exception, e:
            log.error(traceback.format_exc())
            self.lastError = str(e)
        evtiming.serviceLevel.addData('poll', time.time() - t1)

    def updateRules(self):
        try:
            t1 = time.time()
            self.readRules()
            ruleParseTime = time.time() - t1
        except ValueError:
            # this is so if you're just watching the inferred output,
            # you'll see the error too
            self.inferred = Graph()
            self.inferred.add((ROOM['reasoner'], ROOM['ruleParseError'],
                               Literal(traceback.format_exc())))
            raise
        return [(ROOM['reasoner'], ROOM['ruleParseTime'],
                               Literal(ruleParseTime))]

    evtiming.serviceLevel.timed('graphChanged')
    def graphChanged(self, inputGraph, oneShot=False, oneShotGraph=None):
        t1 = time.time()
        oldInferred = self.inferred
        try:
            ruleStmts = self.updateRules()
            
            g = inputGraph.getGraph()
            self.inferred = self._makeInferred(g)
            [self.inferred.add(s) for s in ruleStmts]

            if oneShot:
                # unclear where this should go, but the oneshot'd
                # statements should be just as usable as inferred
                # ones.
                for s in oneShotGraph:
                    self.inferred.add(s)

            t2 = time.time()
            self.actions.putResults(self.inputGraph.getGraph(), self.inferred)
            putResultsTime = time.time() - t2
        finally:
            if oneShot:
                self.inferred = oldInferred
        log.info("graphChanged %.1f ms (putResults %.1f ms)" %
                 ((time.time() - t1) * 1000,
                  putResultsTime * 1000))

    def _makeInferred(self, inputGraph):
        t1 = time.time()
        out = infer(inputGraph, self.ruleStore)
        inferenceTime = time.time() - t1

        out.add((ROOM['reasoner'], ROOM['inferenceTime'],
                 Literal(inferenceTime)))
        return out



class Index(cyclone.web.RequestHandler):
    def get(self):
        print evtiming.serviceLevel.serviceJsonReport()

        # make sure GET / fails if our poll loop died
        ago = time.time() - self.settings.reasoning.lastPollTime
        if ago > 2:
            self.set_status(500)
            self.finish("last poll was %s sec ago. last error: %s" %
                        (ago, self.settings.reasoning.lastError))
            return
        self.set_header("Content-Type", "text/html")
        self.write(open('index.html').read())

class ImmediateUpdate(cyclone.web.RequestHandler):
    @inlineCallbacks
    def put(self):
        """
        request an immediate load of the remote graphs; the thing we
        do in the background anyway. No payload.

        Using PUT because this is idempotent and retryable and
        everything.

        todo: this should do the right thing when many requests come
        in very quickly
        """
        print self.request.headers
        log.info("immediateUpdate from %s",
                 self.request.headers.get('User-Agent', '?'))
        yield r.poll()
        self.set_status(202)

def parseRdf(text, contentType):
    g = Graph()
    g.parse(StringInputSource(text), format={
        'text/n3': 'n3',
        }[contentType])
    return g

class OneShot(cyclone.web.RequestHandler):
    def post(self):
        """
        payload is an rdf graph. The statements are momentarily added
        to the input graph for exactly one update.

        todo: how do we go from a transition like doorclosed-to-open
        to a oneshot event? the upstream shouldn't have to do it. Do
        we make those oneshot events here? for every object change?
        there are probably special cases regarding startup time when
        everything appears to be a 'change'.
        """
        try:
            g = parseRdf(self.request.body, self.request.headers['content-type'])
            for s in g:
                log.debug("oneshot stmt %r", s)
            if not len(g):
                log.warn("incoming oneshot graph had no statements: %r", self.request.body)
                return
            t1 = time.time()
            self.settings.reasoning.inputGraph.addOneShot(g)
            self.set_header('x-graph-ms', str(1000 * (time.time() - t1)))
        except Exception as e:
            log.error(e)
            raise
            
# for reuse
class GraphResource(cyclone.web.RequestHandler):
    def get(self, which):
        self.set_header("Content-Type", "application/json")
        r = self.settings.reasoning
        g = {'lastInput': r.inputGraph.getGraph(),
             'lastOutput': r.inferred,
             }[which]
        self.write(self.jsonRdf(g))

    def jsonRdf(self, g):
        return json.dumps(sorted(list(g)))

class NtGraphs(cyclone.web.RequestHandler):
    """same as what gets posted above"""
    def get(self):
        r = self.settings.reasoning
        inputGraphNt = r.inputGraph.getGraph().serialize(format="nt")
        inferredNt = r.inferred.serialize(format="nt")
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"input": inputGraphNt,
                               "inferred": inferredNt}))

class Rules(cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain")
        self.write(self.settings.reasoning.rulesN3)

class Status(cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain")
        g = self.settings.reasoning.inputGraph.getGraph()
        msg = ""
        for badSource in g.subjects(RDF.type, ROOM['FailedGraphLoad']):
            msg += "GET %s failed (%s). " % (
                badSource, g.value(badSource, ROOM['graphLoadError']))
        if not msg:
            self.finish("all inputs ok")
            return
        self.set_status(500)
        self.finish(msg)

class Static(cyclone.web.RequestHandler):
    def get(self, p):
        self.write(open(p).read())

liveClients = set()
def sendToLiveClients(d=None, asJson=None):
    j = asJson or json.dumps(d)
    for c in liveClients:
        c.sendMessage(j)

class Events(cyclone.websocket.WebSocketHandler):

    def connectionMade(self, *args, **kwargs):
        log.info("websocket opened")
        liveClients.add(self)

    def connectionLost(self, reason):
        log.info("websocket closed")
        liveClients.remove(self)

    def messageReceived(self, message):
        log.info("got message %s" % message)

class Application(cyclone.web.Application):
    def __init__(self, reasoning):
        handlers = [
            (r"/", Index),
            (r"/immediateUpdate", ImmediateUpdate),
            (r"/oneShot", OneShot),
            (r'/(jquery.min.js)', Static),
            (r'/(lastInput|lastOutput)Graph', GraphResource),
            (r'/ntGraphs', NtGraphs),
            (r'/rules', Rules),
            (r'/status', Status),
            (r'/events', Events),
        ]
        cyclone.web.Application.__init__(self, handlers, reasoning=reasoning)

if __name__ == '__main__':

    arg = docopt("""
    Usage: reasoning.py [options]

    -v                Verbose (and slow updates)
    --source=<substr>  Limit sources to those with this string.
    """)
    
    r = Reasoning()
    if arg['-v']:
        from colorlog import ColoredFormatter
        log.handlers[0].setFormatter(ColoredFormatter("%(log_color)s%(levelname)-8s%(reset)s %(white)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%'
))

        import twisted.python.log
        twisted.python.log.startLogging(sys.stdout)
        log.setLevel(logging.DEBUG)
        outlog.setLevel(logging.DEBUG)

    task.LoopingCall(r.poll).start(1.0 if not arg['-v'] else 10)
    reactor.listenTCP(9071, Application(r), interface='::')
    reactor.run()
