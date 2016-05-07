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


import json, time, traceback, sys
from logging import getLogger, DEBUG, WARN

from FuXi.Rete.RuleStore import N3RuleStore
from colorlog import ColoredFormatter
from docopt import docopt
from rdflib import Namespace, Literal, RDF, Graph
from twisted.internet import reactor, task
from twisted.internet.defer import inlineCallbacks
import cyclone.web, cyclone.websocket

from inference import infer
from actions import Actions
from inputgraph import InputGraph

sys.path.append("../../lib")
from logsetup import log


sys.path.append('../../../ffg/ffg')
import evtiming

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")

NS = {'': ROOM, 'dev': DEV}


def unquoteStatement(graph, stmt):
    # todo: use the standard schema for this, or eliminate
    # it in favor of n3 graph literals.
    return (graph.value(stmt, ROOM['subj']),
            graph.value(stmt, ROOM['pred']),
            graph.value(stmt, ROOM['obj']))


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
                 Literal(ruleParseTime))], ruleParseTime

    evtiming.serviceLevel.timed('graphChanged')
    def graphChanged(self, inputGraph, oneShot=False, oneShotGraph=None):
        log.info("----------------------")
        log.info("graphChanged oneShot=%s", oneShot)
        if oneShot:
            for s in oneShotGraph:
                log.debug("oneshot stmt %r", s)
        t1 = time.time()
        oldInferred = self.inferred
        try:
            ruleStatStmts, ruleParseSec = self.updateRules()
            
            g = inputGraph.getGraph()
            self.inferred = self._makeInferred(g)

            for qs in self.inferred.objects(ROOM['output'], ROOM['statement']):
                self.inferred.add(unquoteStatement(self.inferred, qs))
            
            [self.inferred.add(s) for s in ruleStatStmts]

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
        log.info("graphChanged took %.1f ms (rule parse %.1f ms, putResults %.1f ms)" %
                 ((time.time() - t1) * 1000,
                  ruleParseSec * 1000,
                  putResultsTime * 1000))

    def _makeInferred(self, inputGraph):
        t1 = time.time()
        out = infer(inputGraph, self.ruleStore)
        for p, n in NS.iteritems():
            out.bind(p, n, override=True)
        inferenceTime = time.time() - t1

        out.add((ROOM['reasoner'], ROOM['inferenceTime'],
                 Literal(inferenceTime)))
        return out



class Index(cyclone.web.RequestHandler):
    def get(self):
        print evtiming.serviceLevel.serviceJsonReport()

        # make sure GET / fails if our poll loop died
        ago = time.time() - self.settings.reasoning.lastPollTime
        if ago > 15:
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
        log.info("immediateUpdate from %s %s",
                 self.request.headers.get('User-Agent', '?'),
                 self.request.headers['Host'])
        yield r.poll()
        self.set_status(202)

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
            dt = self.settings.reasoning.inputGraph.addOneShotFromString(
                self.request.body, self.request.headers['content-type'])
            self.set_header('x-graph-ms', str(1000 * dt))
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

def configLogging(arg):
    log.setLevel(WARN)
    
    if arg['-i'] or arg['-r'] or arg['-o']:
        log.handlers[0].setFormatter(ColoredFormatter("%(log_color)s%(levelname)-8s %(name)-6s %(filename)-12s:%(lineno)-3s %(funcName)-20s%(reset)s %(white)s%(message)s",
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

    if arg['-i']:
        import twisted.python.log
        twisted.python.log.startLogging(sys.stdout)

    getLogger('fetch').setLevel(DEBUG if arg['-i'] else WARN)
    log.setLevel(DEBUG if arg['-r'] else WARN)
    getLogger('output').setLevel(DEBUG if arg['-o'] else WARN)


if __name__ == '__main__':
    arg = docopt("""
    Usage: reasoning.py [options]

    -i                Verbose log on the input phase (and slow down the polling)
    -r                Verbose log on the reasoning phase and web stuff
    -o                Verbose log on the actions/output phase
    --source=<substr> Limit sources to those with this string.
    """)
    
    r = Reasoning()
    configLogging(arg)
    task.LoopingCall(r.poll).start(1.0 if not arg['-i'] else 10)
    reactor.listenTCP(9071, Application(r), interface='::')
    reactor.run()
