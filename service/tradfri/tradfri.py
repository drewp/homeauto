from __future__ import division
import sys, logging, socket, json, time, os, traceback
import cyclone.web
from cyclone.httpclient import fetch
from rdflib import Namespace, URIRef, Literal, Graph, RDF, RDFS, ConjunctiveGraph
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task
from docopt import docopt
import logging
logging.basicConfig(level=logging.DEBUG)
sys.path.append("/opt")
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from rdfdb.rdflibpatch import inContext
from rdfdb.patch import Patch
from dateutil.tz import tzlocal, tzutc
import private

sys.path.append('pytradfri')
from pytradfri import Gateway
from pytradfri.api.libcoap_api import APIFactory
from pytradfri.const import ATTR_LIGHT_STATE, ATTR_LIGHT_DIMMER

ROOM = Namespace('http://projects.bigasterisk.com/room/')
IKEADEV = Namespace('http://bigasterisk.com/ikeaDevice/')
log = logging.getLogger()

def devUri(dev):
    name = dev.name if dev.name else dev.id
    return IKEADEV['_'.join(w.lower() for w in name.split())]

class Hub(object):
    def __init__(self, graph, ip, key):
        self.graph = graph
        self.ip, self.key = ip, key
        self.api = APIFactory(ip, psk=key)
        self.gateway = Gateway()

        devices_command = self.gateway.get_devices()
        self.devices_commands = self.api.request(devices_command)
        self.devices = self.api.request(self.devices_commands)

        self.ctx = ROOM['tradfriHub']
        self.graph.patch(Patch(
            addQuads=[(s,p,o,self.ctx) for s,p,o in self.deviceStatements()]))

        self.curStmts = []

        task.LoopingCall(self.updateCur).start(60)
        for dev in self.devices:
            self.startObserve(dev)

    def startObserve(self, dev):
        def onUpdate(dev):
            reactor.callFromThread(self.updateCur, dev)
        def onErr(err):
            log.warn('%r; restart observe on %r', err, dev)
            reactor.callLater(1, self.startObserve, dev)
        reactor.callInThread(self.api.request, dev.observe(onUpdate, onErr))

    def description(self):
        return {
            'uri': 'huburi',
            'devices': [{
                'uri': devUri(dev),
                'className': self.__class__.__name__,
                'pinNumber': None,
                'outputPatterns': [(devUri(dev), ROOM['brightness'], None)],
                'watchPrefixes': [],
                'outputWidgets': [{
                    'element': 'output-slider',
                    'min': 0, 'max': 1, 'step': 1 / 255,
                    'subj': devUri(dev),
                    'pred': ROOM['brightness'],
                }] * dev.has_light_control,
            } for dev in self.devices],
            'graph': 'http://sticker:9059/graph', #todo
        }

    def updateCur(self, dev=None):
        cur = [(s,p,o,self.ctx) for s,p,o in
               self.currentStateStatements([dev] if dev else self.devices)]
        self.graph.patch(Patch(addQuads=cur, delQuads=self.curStmts))
        self.curStmts = cur

    def deviceStatements(self):
        for dev in self.devices:
            uri = devUri(dev)
            yield (uri, RDF.type, ROOM['IkeaDevice'])
            yield (uri, ROOM['ikeaId'], Literal(dev.id))
            if dev.last_seen:
                utcSeen = dev.last_seen
                yield (uri, ROOM['lastSeen'],
                       Literal(utcSeen.replace(tzinfo=tzutc()).astimezone(tzlocal())))
                yield (uri, ROOM['reachable'], ROOM['yes'] if dev.reachable else ROOM['no'])
            yield (uri, RDFS.label, Literal(dev.name))
            # no connection between remotes and lights?

    def currentStateStatements(self, devs):
        for dev in self.devices:  # could scan just devs, but the Patch line needs a fix
            uri = devUri(dev)
            di = dev.device_info
            if di.battery_level is not None:
                yield (uri, ROOM['batteryLevel'], Literal(di.battery_level / 100))
            if dev.has_light_control:
                lc = dev.light_control
                #import ipdb;ipdb.set_trace()

                lightUri = devUri(dev)
                print(lc.raw)
                if not lc.raw[0][ATTR_LIGHT_STATE]:
                    level = 0
                else:
                    level = lc.raw[0][ATTR_LIGHT_DIMMER] / 255
                yield (lightUri, ROOM['brightness'], Literal(level))
                #if light.hex_color:
                #    yield (lightUri, ROOM['kelvinColor'], Literal(light.kelvin_color))
                #    yield (lightUri, ROOM['color'], Literal('#%s' % light.hex_color))


    def outputStatements(self, stmts):
        for stmt in stmts:
            for dev in self.devices:
                uri = devUri(dev)
                if stmt[0] == uri:
                    if stmt[1] == ROOM['brightness']:
                        try:
                            self.api.request(dev.light_control.set_dimmer(
                                int(255 * float(stmt[2])), transition_time=3))
                        except:
                            traceback.print_exc()
                            raise
        self.updateCur()

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

        self.settings.hub.outputStatements([stmt])

hostname = socket.gethostname()

class Boards(cyclone.web.RequestHandler):
    def get(self):
        self.set_header('Content-type', 'application/json')
        self.write(json.dumps({
            'host': hostname,
            'boards': [self.settings.hub.description()]
        }, indent=2))

def main():
    arg = docopt("""
    Usage: tradfri.py [options]

    -v   Verbose
    """)
    log.setLevel(logging.WARN)
    if arg['-v']:
        from twisted.python import log as twlog
        twlog.startLogging(sys.stdout)
        log.setLevel(logging.DEBUG)

    masterGraph = PatchableGraph()
    hub = Hub(masterGraph, private.hubAddr, key=private.hubKey)

    reactor.listenTCP(10009, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler, {
            "path": "/opt/static", "default_filename": "index.html"}),
        (r'/static/(.*)', cyclone.web.StaticFileHandler, {"path": "/opt/static"}),
        (r'/boards', Boards),
        (r"/graph/tradfri", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/tradfri/events", CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        ], hub=hub, debug=arg['-v']), interface='::')
    log.warn('serving on 10009')
    reactor.run()

main()
