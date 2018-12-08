from docopt import docopt
from mqtt.client.factory import MQTTFactory
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.parser import StringInputSource
from twisted.application.internet import ClientService, backoffPolicy
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import clientFromString
import cyclone.web
import sys, logging

BROKER = "tcp:bang:1883"
ROOM = Namespace('http://projects.bigasterisk.com/room/')

devs = {
    ROOM['kitchenLight']: {'root': '004BD965', 'ctx': ROOM['kitchenH801']}
}

logging.basicConfig()
log = logging.getLogger()


class MQTTService(ClientService):

    def __init(self, endpoint, factory):
        ClientService.__init__(self, endpoint, factory, retryPolicy=backoffPolicy())

    def startService(self):
        self.whenConnected().addCallback(self.connectToBroker)
        ClientService.startService(self)

    @inlineCallbacks
    def connectToBroker(self, protocol):
        self.protocol = protocol
        self.protocol.onDisconnection = self.onDisconnection
        # We are issuing 3 publish in a row
        # if order matters, then set window size to 1
        # Publish requests beyond window size are enqueued
        self.protocol.setWindowSize(1)

        try:
            yield self.protocol.connect("TwistedMQTT-pub", keepalive=60)
        except Exception as e:
            log.error("Connecting to {broker} raised {excp!s}",
                      broker=BROKER, excp=e)
        else:
            log.info("Connected to {broker}".format(broker=BROKER))

    def onDisconnection(self, reason):
        log.warn("Connection to broker lost: %r", reason)
        self.whenConnected().addCallback(self.connectToBroker)

    def publish(self, topic, msg):
        def _logFailure(failure):
            log.warn("publish failed: %s", failure.getErrorMessage())
            return failure

        return self.protocol.publish(topic=topic, qos=0, message=msg).addErrback(_logFailure)

def rdfGraphBody(body, headers):
    g = Graph()
    g.parse(StringInputSource(body), format='nt')
    return g

class OutputPage(cyclone.web.RequestHandler):
    def put(self):
        arg = self.request.arguments
        if arg.get('s') and arg.get('p'):
            subj = URIRef(arg['s'][-1])
            pred = URIRef(arg['p'][-1])
            turtleLiteral = self.request.body
            try:
                obj = Literal(float(turtleLiteral))
            except ValueError:
                obj = Literal(turtleLiteral)
            stmt = (subj, pred, obj)
        else:
            g = rdfGraphBody(self.request.body, self.request.headers)
            assert len(g) == 1, len(g)
            stmt = g.triples((None, None, None)).next()
        self._onStatement(stmt)
            
    def _onStatement(self, stmt):
        for dev, attrs in devs.items():
            if stmt[0:2] == (dev, ROOM['brightness']):
                sw = 'OFF' if stmt[2].toPython() == 0 else 'ON'
                serv.publish("%s/w1/light/switch" % attrs['root'], sw)
                self.settings.masterGraph.patchObject(attrs['ctx'],
                                                      stmt[0], stmt[1], stmt[2])
                return
        log.warn("ignoring %s", stmt)
            
if __name__ == '__main__':
    arg = docopt("""
    Usage: mqtt_graph_bridge.py [options]

    -v   Verbose
    """)
    log.setLevel(logging.WARN)
    if arg['-v']:
        from twisted.python import log as twlog
        twlog.startLogging(sys.stdout)
        log.setLevel(logging.DEBUG)

    masterGraph = PatchableGraph()

    factory    = MQTTFactory(profile=MQTTFactory.PUBLISHER)
    myEndpoint = clientFromString(reactor, BROKER)
    serv       = MQTTService(myEndpoint, factory)

    port = 10008
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler,
         {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        ], serv=serv, masterGraph=masterGraph, debug=arg['-v']), interface='::')
    log.warn('serving on %s', port)

    for dev, attrs in devs.items():
        masterGraph.patchObject(attrs['ctx'],
                                dev, ROOM['brightness'], Literal(0.0))
    
    serv.startService()
    reactor.run()
