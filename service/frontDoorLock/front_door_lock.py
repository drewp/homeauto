"""
:frontDoorLock :state :locked/:unlocked
is the true state of the lock, maintained in this process.

put :frontDoorLock :state ?s to this /output to request a change.

reasoning can infer :frontDoorLock :putState ?s to do that put request.
"""
import time, json

from docopt import docopt
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task
import cyclone.web

from mqtt_client import MqttClient
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from standardservice.logsetup import log, verboseLogging

ROOM = Namespace('http://projects.bigasterisk.com/room/')

ctx = ROOM['frontDoorControl']
espName = b'frontdoorlock' # from door.yaml

def rdfGraphBody(body, headers):
    g = Graph()
    g.parse(StringInputSource(body), format='nt')
    return g

def mqttMessageFromState(state: URIRef):
    return {
        ROOM['locked']: b'OFF',
        ROOM['unlocked']: b'ON',
        }[state]

def stateFromMqtt(msg: bytes):
    return {
        b'OFF': ROOM['locked'],
        b'ON': ROOM['unlocked'],
    }[bytes(msg)]
    
class OutputPage(cyclone.web.RequestHandler):
    def put(self):
        try:
            # what happened to the case-insens dict?
            h = dict((k.lower(), v) for k,v in self.request.headers.items())
            user = URIRef(h['x-foaf-agent'])
        except KeyError:
            log.warn('request without x-foaf-agent: %s', h)
            self.set_status(403, 'need x-foaf-agent')
            return
        arg = self.request.arguments
        if arg.get('s') and arg.get('p'):
            subj = URIRef(arg['s'][-1])
            pred = URIRef(arg['p'][-1])
            obj = URIRef(self.request.body.strip().decode('ascii'))
            stmt = (subj, pred, obj)
        else:
            g = rdfGraphBody(self.request.body, self.request.headers)
            assert len(g) == 1, len(g)
            stmt = next(g.triples((None, None, None)))
        self._onStatement(user, stmt)
    post = put
    
    def _onStatement(self, user, stmt):
        log.info('put statement %r', stmt)
        if stmt[0:2] == (ROOM['frontDoorLock'], ROOM['state']):
            if stmt[2] == ROOM['unlocked']:
                log.info('unlock for %r', user)
                self.settings.autoLock.onUnlockedStmt()
            if stmt[2] == ROOM['locked']:
                self.settings.autoLock.onLockedStmt()
            self.settings.mqtt.publish(espName + b"/switch/strike/command",
                                       mqttMessageFromState(stmt[2]))
            return
        log.warn("ignoring %s", stmt)


class AutoLock(object):
    def __init__(self, masterGraph, mqtt):
        self.masterGraph = masterGraph
        self.mqtt = mqtt
        self.timeUnlocked = None
        self.autoLockSec = 6 
        self.subj = ROOM['frontDoorLock']
        task.LoopingCall(self.pollCheck).start(1)

    def relock(self):
        log.info('autolock is up: requesting lock')
        self.mqtt.publish(espName + b"/switch/strike/command",
                          mqttMessageFromState(ROOM['locked']))

    def reportTimes(self, unlockedFor):
        g = self.masterGraph
        lockIn = self.autoLockSec - int(unlockedFor)
        if lockIn < 0:
            state = g._graph.value(self.subj, ROOM['state'])
            log.warn(f"timeUnlocked {self.timeUnlocked}, state {state}, "
                     "unlockedFor {unlockedFor}, lockIn {lockIn}")
            lockIn = 0
        g.patchObject(ctx, self.subj, ROOM['unlockedForSec'],
                      Literal(int(unlockedFor)))
        g.patchObject(ctx, self.subj, ROOM['autoLockInSec'],
                      Literal(lockIn))

    def clearReport(self):
        g = self.masterGraph
        g.patchObject(ctx, self.subj, ROOM['unlockedForSec'], None)
        g.patchObject(ctx, self.subj, ROOM['autoLockInSec'], None)

    def pollCheck(self):
        try:
            self.check()
        except Exception:
            log.exception('poll failed')
        
    def check(self):
        g = self.masterGraph
        now = time.time()
        state = g._graph.value(self.subj, ROOM['state'])
        if state == ROOM['unlocked']:
            if self.timeUnlocked is None:
                self.timeUnlocked = now
            # *newly* unlocked- this resets on every input stmt
            unlockedFor = now - self.timeUnlocked
            if unlockedFor > self.autoLockSec:
                self.relock()
        else:
            self.timeUnlocked = None
            unlockedFor = 0
        if unlockedFor > 3:
            # only start showing the count if it looks like we're not
            # being repeatedly held open. Time is hopefully more than
            # the refresh rate of "reasoning.actions".
            self.reportTimes(unlockedFor)
        else:
            self.clearReport()

    def onUnlockedStmt(self):
        self.timeUnlocked = None
        
    def onLockedStmt(self):
        pass

class BluetoothButton(cyclone.web.RequestHandler):
    def post(self):
        body = json.loads(self.request.body)
        log.info('POST bluetoothButton %r', body)
        if body['addr'] == 'zz:zz:zz:zz:zz:zz' and body['key'] == 'top':
            log.info('unlock for %r', body['addr'])
            self.settings.mqtt.publish(
                espName + b"/switch/strike/command", b'ON')

            
if __name__ == '__main__':
    arg = docopt("""
    Usage: front_door_lock.py [options]

    -v   Verbose
    """)
    verboseLogging(arg['-v'])

    masterGraph = PatchableGraph()
    mqtt = MqttClient(brokerPort=10010)
    autoclose = AutoLock(masterGraph, mqtt)

    def toGraph(payload):
        log.info('mqtt->graph %r', payload)
        masterGraph.patchObject(ctx, ROOM['frontDoorLock'], ROOM['state'],
                                stateFromMqtt(payload))

    mqtt.subscribe(espName + b"/switch/strike/state").subscribe(on_next=toGraph)

    def setEspState(payload):
        log.info('esp state change %r', payload)
        masterGraph.patchObject(ctx, ROOM['frontDoorLock'], ROOM['espMqttConnection'],
                                ROOM['mqtt' + payload.decode('ascii').capitalize()])
    
    mqtt.subscribe(espName + b"/status").subscribe(on_next=setEspState)
    
    port = 10011
    reactor.listenTCP(port, cyclone.web.Application(
        [
            (r"/()", cyclone.web.StaticFileHandler,
             {"path": ".", "default_filename": "index.html"}),
            (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
            (r"/graph/events", CycloneGraphEventsHandler,
             {'masterGraph': masterGraph}),
            (r'/output', OutputPage),
            (r'/bluetoothButton', BluetoothButton),
        ],
        mqtt=mqtt,
        masterGraph=masterGraph,
        autoLock=autoclose,
        debug=arg['-v']),
                      interface='::')
    log.warn('serving on %s', port)

    reactor.run()
