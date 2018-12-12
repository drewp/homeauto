from docopt import docopt
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.parser import StringInputSource
from twisted.internet import reactor
import cyclone.web
import sys, logging
from mqtt_client import MqttClient

ROOM = Namespace('http://projects.bigasterisk.com/room/')

logging.basicConfig()
log = logging.getLogger()

ctx = ROOM['frontDoorControl']

def rdfGraphBody(body, headers):
    g = Graph()
    g.parse(StringInputSource(body), format='nt')
    return g

def mqttMessageFromState(state):
    return {
        ROOM['locked']: b'OFF',
        ROOM['unlocked']: b'ON',
        }[state]

def stateFromMqtt(msg):
    return {
        'OFF': ROOM['locked'],
        'ON': ROOM['unlocked'],
    }[msg.decode('ascii')]
    
class OutputPage(cyclone.web.RequestHandler):
    def put(self):
        arg = self.request.arguments
        if arg.get('s') and arg.get('p'):
            subj = URIRef(arg['s'][-1])
            pred = URIRef(arg['p'][-1])
            obj = URIRef(self.request.body)
            stmt = (subj, pred, obj)
        else:
            g = rdfGraphBody(self.request.body, self.request.headers)
            assert len(g) == 1, len(g)
            stmt = g.triples((None, None, None)).next()
        self._onStatement(stmt)
            
    def _onStatement(self, stmt):
        if stmt[0:2] == (ROOM['frontDoorLock'], ROOM['state']):
            self.settings.mqtt.publish("frontdoor/switch/strike/command",
                                       mqttMessageFromState(stmt[2]))
            self.settings.masterGraph.patchObject(ctx,
                                                  stmt[0], stmt[1], stmt[2])
            return
        log.warn("ignoring %s", stmt)
            
if __name__ == '__main__':
    arg = docopt("""
    Usage: front_door_lock.py [options]

    -v   Verbose
    """)
    log.setLevel(logging.WARN)
    if arg['-v']:
        from twisted.python import log as twlog
        twlog.startLogging(sys.stdout)
        log.setLevel(logging.DEBUG)

    masterGraph = PatchableGraph()
    mqtt = MqttClient(brokerPort=10010)

    def toGraph(payload):
        log.debug('toGraph %r', payload)
        masterGraph.patchObject(ctx, ROOM['frontDoorLock'], ROOM['state'],
                                stateFromMqtt(payload))

    mqtt.subscribe("frontdoor/switch/strike/state").subscribe(on_next=toGraph)
    port = 10011
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler,
         {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        ], mqtt=mqtt, masterGraph=masterGraph, debug=arg['-v']), interface='::')
    log.warn('serving on %s', port)

    reactor.run()
