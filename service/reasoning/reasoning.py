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


from crochet import no_setup
no_setup()


import json, time, traceback, sys
from logging import getLogger, DEBUG, WARN

from colorlog import ColoredFormatter
from docopt import docopt
from rdflib import Namespace, Literal, RDF, Graph
from twisted.internet import reactor, task
from twisted.internet.defer import inlineCallbacks
import cyclone.web, cyclone.websocket

from greplin import scales
from greplin.scales.cyclonehandler import StatsHandler

from inference import infer, readRules
from actions import Actions
from inputgraph import InputGraph
from escapeoutputstatements import unquoteOutputStatements

sys.path.append("../../lib")
from logsetup import log


ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")

NS = {'': ROOM, 'dev': DEV}

STATS = scales.collection('/web',
                          scales.PmfStat('graphChanged'))

class Reasoning(object):
    def __init__(self):
        self.prevGraph = None

        self.actions = Actions(sendToLiveClients)

        self.rulesN3 = "(not read yet)"
        self.inferred = Graph() # gets replaced in each graphChanged call

        self.inputGraph = InputGraph([], self.graphChanged)      
        self.inputGraph.updateFileData()

    def updateRules(self):
        rulesPath = 'rules.n3'
        try:
            t1 = time.time()
            self.rulesN3, self.ruleStore = readRules(
                rulesPath, outputPatterns=[
                    # Incomplete. See escapeoutputstatements.py for
                    # explanation.
                    (None, ROOM['brightness'], None),
                    (None, ROOM['playState'], None),
                    (None, ROOM['powerState'], None),
                    (None, ROOM['state'], None),
                ])
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

    @STATS.graphChanged.time()
    def graphChanged(self, inputGraph, oneShot=False, oneShotGraph=None):
        """
        If we're getting called for a oneShot event, the oneShotGraph
        statements are already in inputGraph.getGraph().
        """
        log.info("----------------------")
        log.info("graphChanged (oneShot=%s):", oneShot)
        t1 = time.time()
        oldInferred = self.inferred
        try:
            ruleStatStmts, ruleParseSec = self.updateRules()

            self.inferred, inferSec = self._makeInferred(inputGraph.getGraph())

            self.inferred += unquoteOutputStatements(self.inferred)

            self.inferred += ruleStatStmts

            if oneShot:
                # It's possible a oneShotGraph statement didn't
                # trigger a rule to do something, but was itself the
                # output statement. Probably we could just mix in the
                # whole inputGraph here and not special-case the
                # oneShotGraph.
                self.inferred += oneShotGraph

            t3 = time.time()
            self.actions.putResults(self.inputGraph.getGraph(), self.inferred)
            putResultsTime = time.time() - t3
        finally:
            if oneShot:
                self.inferred = oldInferred
        log.info("graphChanged took %.1f ms (rule parse %.1f ms, infer %.1f ms, putResults %.1f ms)" %
                 ((time.time() - t1) * 1000,
                  ruleParseSec * 1000,
                  inferSec * 1000,
                  putResultsTime * 1000))

    def _makeInferred(self, inputGraph):
        t1 = time.time()

        out = infer(inputGraph, self.ruleStore)
        for p, n in NS.iteritems():
            out.bind(p, n, override=True)

        inferenceTime = time.time() - t1
        out.add((ROOM['reasoner'], ROOM['inferenceTime'],
                 Literal(inferenceTime)))
        return out, inferenceTime


        
class Index(cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/html")
        self.write(open('index.html').read())

class ImmediateUpdate(cyclone.web.RequestHandler):
    def put(self):
        """
        request an immediate load of the remote graphs; the thing we
        do in the background anyway. No payload.

        Using PUT because this is idempotent and retryable and
        everything.

        todo: this should do the right thing when many requests come
        in very quickly
        """
        log.warn("immediateUpdate from %s %s - ignored",
                 self.request.headers.get('User-Agent', '?'),
                 self.request.headers['Host'])
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
            (r'/stats/(.*)', StatsHandler, {'serverName': 'reasoning'}),
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

    -i                Verbose log on the input phase
    -r                Verbose log on the reasoning phase and web stuff
    -o                Verbose log on the actions/output phase
    --source=<substr> Limit sources to those with this string.
    """)
    
    r = Reasoning()
    configLogging(arg)
    reactor.listenTCP(9071, Application(r), interface='::')
    reactor.run()
