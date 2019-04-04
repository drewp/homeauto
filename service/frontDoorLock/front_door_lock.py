"""
:frontDoorLock :state :locked/:unlocked
is the true state of the lock, maintained in this process.

put :frontDoorLock :state ?s to this /output to request a change.

reasoning can infer :frontDoorLock :putState ?s to do that put request.
"""
from docopt import docopt
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task
import cyclone.web
import sys, logging, time
from mqtt_client import MqttClient
from logsetup import log, enableTwistedLog

ROOM = Namespace('http://projects.bigasterisk.com/room/')

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
    post = put
    
    def _onStatement(self, stmt):
        if stmt[0:2] == (ROOM['frontDoorLock'], ROOM['state']):
            self.settings.mqtt.publish("frontdoor/switch/strike/command",
                                       mqttMessageFromState(stmt[2]))
            return
        log.warn("ignoring %s", stmt)


class AutoLock(object):
    def __init__(self, masterGraph, mqtt):
        self.masterGraph = masterGraph
        self.mqtt = mqtt
        self.timeUnlocked = None
        self.autoLockSec = 5
        self.subj = ROOM['frontDoorLock']
        task.LoopingCall(self.check).start(1)

    def check(self):
        now = time.time()
        state = self.masterGraph._graph.value(self.subj, ROOM['state'])
        if state == ROOM['unlocked']:
            if self.timeUnlocked is None:
                self.timeUnlocked = now
            unlockedFor = now - self.timeUnlocked
            self.masterGraph.patchObject(ctx, self.subj, ROOM['unlockedForSec'],
                                         Literal(int(unlockedFor)))
            self.masterGraph.patchObject(ctx, self.subj, ROOM['autoLockInSec'],
                                         Literal(self.autoLockSec - int(unlockedFor)))
            if unlockedFor > self.autoLockSec:
                self.mqtt.publish("frontdoor/switch/strike/command",
                                  mqttMessageFromState(ROOM['locked']))
        else:
            self.timeUnlocked = None
            self.masterGraph.patchObject(ctx, self.subj, ROOM['unlockedForSec'], None)
            self.masterGraph.patchObject(ctx, self.subj, ROOM['autoLockInSec'], None)

            
if __name__ == '__main__':
    arg = docopt("""
    Usage: front_door_lock.py [options]

    -v   Verbose
    """)
    log.setLevel(logging.INFO)
    if arg['-v']:
        enableTwistedLog()
        log.setLevel(logging.DEBUG)

    masterGraph = PatchableGraph()
    mqtt = MqttClient(brokerPort=10010)
    autoclose = AutoLock(masterGraph, mqtt)

    def toGraph(payload):
        log.info('mqtt->graph %r', payload)
        masterGraph.patchObject(ctx, ROOM['frontDoorLock'], ROOM['state'],
                                stateFromMqtt(payload))

    mqtt.subscribe("frontdoor/switch/strike/state").subscribe(on_next=toGraph)
    port = 10011
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler,
         {"path": ".", "default_filename": "index.html"}),
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler,
         {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        ], mqtt=mqtt, masterGraph=masterGraph, debug=arg['-v']), interface='::')
    log.warn('serving on %s', port)

    reactor.run()
