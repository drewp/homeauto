from docopt import docopt
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.parser import StringInputSource
from twisted.internet import reactor
import cyclone.web
import sys, logging, json
from mqtt_client import MqttClient

ROOM = Namespace('http://projects.bigasterisk.com/room/')

devs = {
    ROOM['kitchenLight']: {
        'root': 'h801_skylight',
        'ctx': ROOM['kitchenH801']
    },
    ROOM['kitchenCounterLight']: {
        'root': 'h801_counter',
        'ctx': ROOM['kitchenH801']
    },
}

logging.basicConfig()
log = logging.getLogger()

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
        ignored = True
        for dev, attrs in devs.items():
            if stmt[0:2] == (dev, ROOM['brightness']):
                for chan, scale in [('w1', 1),
                                    ('r', 1),
                                    ('g', .8),
                                    ('b', .8)]:
                    out = stmt[2].toPython() * scale 
                    self.settings.mqtt.publish(
                        "%s/light/kit_%s/command" % (attrs['root'], chan),
                        json.dumps({
                            'state': 'ON',
                            'brightness': int(out * 255)}))
                self.settings.masterGraph.patchObject(
                    attrs['ctx'],
                    stmt[0], stmt[1], stmt[2])
                ignored = False
        if ignored:
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

    mqtt = MqttClient(brokerPort=1883)

    port = 10008
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler,
         {"path": ".", "default_filename": "index.html"}),
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler,
         {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        ], mqtt=mqtt, masterGraph=masterGraph, debug=arg['-v']), interface='::')
    log.warn('serving on %s', port)

    for dev, attrs in devs.items():
        masterGraph.patchObject(attrs['ctx'],
                                dev, ROOM['brightness'], Literal(0.0))
    
    
    reactor.run()
