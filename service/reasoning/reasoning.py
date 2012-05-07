#!bin/python
"""
gather subgraphs from various services, run them through a rules
engine, and make http requests with the conclusions.

E.g. 'when drew's phone is near the house, and someone is awake,
unlock the door when the door's motion sensor is activated'

When do we gather? The services should be able to trigger us, perhaps
with PSHB, that their graph has changed.
"""


from twisted.internet import reactor, task
from twisted.web.client import getPage
import time, traceback, sys, json
from rdflib.Graph import Graph, ConjunctiveGraph
from rdflib import Namespace, URIRef,  Literal
import restkit
from FuXi.Rete.RuleStore import N3RuleStore
import cyclone.web
from inference import addTrig, infer

sys.path.append("../../lib")
from logsetup import log

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")

def gatherGraph():
    g = ConjunctiveGraph()
    for source in ["http://bang:9069/graph", # arduino watchpins 
                   "http://bang:9070/graph", # wifi usage
                   "http://bang:9075/graph", # env
                   "http://slash:9050/graph", # garageArduino for front motion
                   "http://dash:9095/graph", # dash monitor
                   "http://bang:9095/graph", # bang monitor
                   ]:
        try:
            addTrig(g, source)
        except:
            log.error("adding source %s", source)
            raise

    return g

def graphWithoutMetadata(g, ignorePredicates=[]):
    """
    graph filter that removes any statements whose subjects are
    contexts in the graph and also any statements with the given
    predicates
    """
    ctxs = map(URIRef, set(g.contexts())) # weird they turned to strings

    out = ConjunctiveGraph()
    for stmt in g.quads((None, None, None)):
        if stmt[0] not in ctxs and stmt[1] not in ignorePredicates:
            out.addN([stmt])
    return out

def graphEqual(a, b, ignorePredicates=[]):
    """
    compare graphs, omitting any metadata statements about contexts
    (especially modification times) and also any statements using the
    given predicates
    """
    stmtsA = graphWithoutMetadata(a, ignorePredicates)
    stmtsB = graphWithoutMetadata(b, ignorePredicates)
    return set(stmtsA) == set(stmtsB)    

class Reasoning(object):
    def __init__(self):
        self.prevGraph = None
        self.lastPollTime = 0
        self.lastError = ""

        self.deviceGraph = Graph()
        self.deviceGraph.parse("/my/proj/room/devices.n3", format="n3")

        self.rulesN3 = "(not read yet)"
        self.inferred = Graph() # gets replaced in each graphChanged call

    def readRules(self):
        self.rulesN3 = open('rules.n3').read() # for web display
        self.ruleStore = N3RuleStore()
        self.ruleGraph = Graph(self.ruleStore)
        self.ruleGraph.parse('rules.n3', format='n3') # for inference

    def poll(self):
        try:
            self._poll()
            self.lastPollTime = time.time()
        except Exception, e:
            log.error(traceback.format_exc())
            self.lastError = str(e)

    def _poll(self):
        g = gatherGraph()
        if (self.prevGraph is None or
            not graphEqual(g, self.prevGraph,
                           ignorePredicates=[ROOM.signalStrength])):
            self.graphChanged(g)

        self.prevGraph = g

    def graphChanged(self, g):
        # i guess these are getting consumed each inference
        try:
            t1 = time.time()
            self.readRules()
            ruleParseTime = time.time() - t1
        except ValueError, e:
            # this is so if you're just watching the inferred output,
            # you'll see the error too
            self.inferred = Graph()
            self.inferred.add((ROOM['reasoner'], ROOM['ruleParseError'],
                               Literal(traceback.format_exc())))
            raise

        t1 = time.time()
        self.inferred = infer(g, self.ruleStore)
        inferenceTime = time.time() - t1

        self.inferred.add((ROOM['reasoner'], ROOM['ruleParseTime'],
                           Literal(ruleParseTime)))
        self.inferred.add((ROOM['reasoner'], ROOM['inferenceTime'],
                           Literal(inferenceTime)))

        self.putResults(self.inferred)
        
        try:
            inputGraphNt = g.serialize(format="nt")
            inferredNt = self.inferred.serialize(format="nt")
            body = json.dumps({"input": inputGraphNt,
                               "inferred": inferredNt})
            restkit.Resource("http://bang:8014/").post(
                "reasoningChange", payload=body,
                headers={"content-type" : "application/json"})
        except Exception, e:
            traceback.print_exc()
            log.error("while sending changes to magma:")
            log.error(e)
            

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

        for dev, pred in [
            # the config of each putUrl should actually be in the
            # context of a dev and predicate pair, and then that would
            # be the source of this list
            (DEV.theaterDoorLock, ROOM.state),
            (URIRef('http://bigasterisk.com/host/bang/monitor'), ROOM.powerState),
            ]:
            url = self.deviceGraph.value(dev, ROOM.putUrl)

            if dev == DEV.theaterDoorLock: # ew
                restkit.request(url=url+"/mode", method="PUT", body="output")

            inferredObjects = list(inferred.objects(dev, pred))
            if len(inferredObjects) == 0:
                self.putZero(dev, pred, url)
            elif len(inferredObjects) == 1:
                self.putInferred(dev, pred, url, inferredObjects[0])
            elif len(inferredObjects) > 1:
                log.info("conflict, ignoring: %s has %s of %s" %
                         (dev, pred, inferredObjects))
                # write about it to the inferred graph?
            
        self.frontDoorPuts(inferred)

    def putZero(self, dev, pred, putUrl):
        # zerovalue should be a function of pred as well.
        value = self.deviceGraph.value(dev, ROOM.zeroValue)
        if value is not None:
            log.info("put zero (%r) to %s", value, putUrl)
            restkit.request(url=putUrl, method="PUT", body=value)
            # this should be written back into the inferred graph
            # for feedback

    def putInferred(self, dev, pred, putUrl, obj):
        value = self.deviceGraph.value(obj, ROOM.putValue)
        if value is not None:
            log.info("put %s to %s", value, putUrl)
            restkit.request(url=putUrl, method="PUT", body=value)
        else:
            log.warn("%s %s %s has no :putValue" %
                     (dev, pred, obj))
        
    def frontDoorPuts(self, inferred):
        # todo: shouldn't have to be a special case
        brt = inferred.value(DEV.frontDoorLcd, ROOM.brightness)
        url = self.deviceGraph.value(DEV.frontDoorLcdBrightness,
                                       ROOM.putUrl)
        log.info("put lcd %s brightness %s", url, brt)
        getPage(str(url) + "?brightness=%s" % str(brt), method="PUT")

        msg = "open %s motion %s" % (inferred.value(DEV['frontDoorOpenIndicator'], ROOM.text),
                                     inferred.value(DEV['frontDoorMotionIndicator'], ROOM.text))
        # this was meant to be 2 chars in the bottom row, but the
        # easier test was to replace the whole top msg
        #restkit.Resource("http://slash:9080/").put("lcd", message=msg)


class Index(cyclone.web.RequestHandler):
    def get(self):
        # make sure GET / fails if our poll loop died
        ago = time.time() - self.settings.reasoning.lastPollTime
        if ago > 2:
            self.set_status(500)
            self.finish("last poll was %s sec ago. last error: %s" %
                        (ago, self.settings.reasoning.lastError))
            return
        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(open('index.html').read())

# for reuse
class GraphResource(cyclone.web.RequestHandler):
    def get(self, which):
        self.set_header("Content-Type", "application/json")
        r = self.settings.reasoning
        g = {'lastInput': r.prevGraph,
             'lastOutput': r.inferred,
             }[which]
        self.write(self.jsonRdf(g))

    def jsonRdf(self, g):
        return json.dumps(sorted(list(g)))

class NtGraphs(cyclone.web.RequestHandler):
    """same as what gets posted above"""
    def get(self):
        r = self.settings.reasoning
        inputGraphNt = r.prevGraph.serialize(format="nt")
        inferredNt = r.inferred.serialize(format="nt")
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"input": inputGraphNt,
                               "inferred": inferredNt}))

class Rules(cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain")
        self.write(self.settings.reasoning.rulesN3)

class Static(cyclone.web.RequestHandler):
    def get(self, p):
        self.write(open(p).read())
        
class Application(cyclone.web.Application):
    def __init__(self, reasoning):
        handlers = [
            (r"/", Index),
            (r'/(jquery.min.js)', Static),
            (r'/(lastInput|lastOutput)Graph', GraphResource),
            (r'/ntGraphs', NtGraphs),
            (r'/rules', Rules),
        ]
        cyclone.web.Application.__init__(self, handlers, reasoning=reasoning)

if __name__ == '__main__':
    r = Reasoning()
    #import twisted.python.log
    #twisted.python.log.startLogging(sys.stdout)
    
    task.LoopingCall(r.poll).start(1.0)
    reactor.listenTCP(9071, Application(r))
    reactor.run()
