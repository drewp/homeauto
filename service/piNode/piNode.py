from __future__ import division
import sys, logging, socket, json, time, os
import cyclone.web
from cyclone.httpclient import fetch
from rdflib import Namespace, URIRef, Literal, Graph, RDF, ConjunctiveGraph
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task
from docopt import docopt

logging.basicConfig(level=logging.DEBUG)
sys.path.append("/opt/homeauto_lib")
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from light9.rdfdb.rdflibpatch import inContext
from light9.rdfdb.patch import Patch
sys.path.append('/opt/pigpio')
try:
    import pigpio
except ImportError:
    class pigpio(object):
        @staticmethod
        def pi():
            return None

import devices

# from /my/proj/room
from carbondata import CarbonClient

log = logging.getLogger()
logging.getLogger('serial').setLevel(logging.WARN)

ROOM = Namespace('http://projects.bigasterisk.com/room/')
HOST = Namespace('http://bigasterisk.com/ruler/host/')

hostname = socket.gethostname()

CTX = ROOM['pi/%s' % hostname]

def patchRandid():
    """
    I'm concerned urandom is slow on raspberry pi, and I'm adding to
    graphs a lot. Unclear what the ordered return values might do to
    the balancing of the graph.
    """
    _id_serial = [1000]
    def randid():
        _id_serial[0] += 1
        return _id_serial[0]
    import rdflib.plugins.memory
    rdflib.plugins.memory.randid = randid
patchRandid()

class Config(object):
    def __init__(self, masterGraph):
        self.graph = ConjunctiveGraph()
        log.info('read config')
        for f in os.listdir('config'):
            if f.startswith('.'): continue
            self.graph.parse('config/%s' % f, format='n3')
            log.info('  parsed %s', f)
        self.graph.bind('', ROOM)
        self.graph.bind('rdf', RDF)
        # config graph is too noisy; maybe make it a separate resource
        #masterGraph.patch(Patch(addGraph=self.graph))

class Board(object):
    """similar to arduinoNode.Board but without the communications stuff"""
    def __init__(self, graph, masterGraph, uri):
        self.graph, self.uri = graph, uri
        self.masterGraph = masterGraph
        self.masterGraph.patch(Patch(addQuads=self.staticStmts()))
        self.pi = pigpio.pi()
        self._devs = devices.makeDevices(graph, self.uri, self.pi)
        log.debug('found %s devices', len(self._devs))
        self._statementsFromInputs = {} # input device uri: latest statements
        self._lastPollTime = {} # input device uri: time()
        self._carbon = CarbonClient(serverHost='bang')
        for d in self._devs:
            self.syncMasterGraphToHostStatements(d)
            
    def startPolling(self):
        task.LoopingCall(self._poll).start(.05)

    def _poll(self):
        for i in self._devs:
            now = time.time()
            if (hasattr(i, 'pollPeriod') and
                self._lastPollTime.get(i.uri, 0) + i.pollPeriod > now):
                continue
            new = i.poll()
            if isinstance(new, dict): # new style
                oneshot = new['oneshot']
                new = new['latest']
            else:
                oneshot = None
            prev = self._statementsFromInputs.get(i.uri, [])

            if new or prev:
                self._statementsFromInputs[i.uri] = new
                # it's important that quads from different devices
                # don't clash, since that can lead to inconsistent
                # patches (e.g.
                #   dev1 changes value from 1 to 2;
                #   dev2 changes value from 2 to 3;
                #   dev1 changes from 2 to 4 but this patch will
                #     fail since the '2' statement is gone)
                self.masterGraph.patch(Patch.fromDiff(inContext(prev, i.uri),
                                                      inContext(new, i.uri)))

            if oneshot:
                self._sendOneshot(oneshot)
            self._lastPollTime[i.uri] = now
        self._exportToGraphite()

    def _sendOneshot(self, oneshot):
        body = (' '.join('%s %s %s .' % (s.n3(), p.n3(), o.n3())
                         for s,p,o in oneshot)).encode('utf8')
        bang6 = 'fcb8:4119:fb46:96f8:8b07:1260:0f50:fcfa'
        fetch(method='POST',
              url='http://[%s]:9071/oneShot' % bang6,
              headers={'Content-Type': ['text/n3']}, postdata=body,
              timeout=5)

    def _exportToGraphite(self):
        # note this is writing way too often- graphite is storing at a lower res
        now = time.time()
        # 20 sec is not precise; just trying to reduce wifi traffic
        if getattr(self, 'lastGraphiteExport', 0) + 20 > now:
            return
        self.lastGraphiteExport = now
        log.debug('graphite export:')
        # objects of these statements are suitable as graphite values.
        graphitePredicates = {ROOM['temperatureF']}
        # bug: one sensor can have temp and humid- this will be ambiguous
        for s, graphiteName in self.graph.subject_objects(ROOM['graphiteName']):
            for group in self._statementsFromInputs.values():
                for stmt in group:
                    if stmt[0] == s and stmt[1] in graphitePredicates:
                        log.debug('  sending %s -> %s', stmt[0], graphiteName)
                        self._carbon.send(graphiteName, stmt[2].toPython(), now)

    def outputStatements(self, stmts):
        unused = set(stmts)
        for dev in self._devs:
            stmtsForDev = []
            for pat in dev.outputPatterns():
                if [term is None for term in pat] != [False, False, True]:
                    raise NotImplementedError
                for stmt in stmts:
                    if stmt[:2] == pat[:2]:
                        stmtsForDev.append(stmt)
                        unused.discard(stmt)
            if stmtsForDev:
                log.info("output goes to action handler for %s" % dev.uri)
                dev.sendOutput(stmtsForDev)

                # Dev *could* change hostStatements at any time, and
                # we're not currently tracking that, but the usual is
                # to change them in response to sendOutput so this
                # should be good enough. The right answer is to give
                # each dev the masterGraph for it to write to.
                self.syncMasterGraphToHostStatements(dev)
                log.info("output and masterGraph sync complete")
        if unused:
            log.info("Board %s doesn't care about these statements:", self.uri)
            for s in unused:
                log.warn("%r", s)

    def syncMasterGraphToHostStatements(self, dev):
        hostStmtCtx = URIRef(dev.uri + '/host')
        newQuads = inContext(dev.hostStatements(), hostStmtCtx)
        p = self.masterGraph.patchSubgraph(hostStmtCtx, newQuads)
        log.debug("patch master with these host stmts %s", p)

    def staticStmts(self):
        return [(HOST[hostname], ROOM['connectedTo'], self.uri, CTX)]

    def description(self):
        """for web page"""
        return {
            'uri': self.uri,
            'devices': [d.description() for d in self._devs],
            'graph': 'http://sticker:9059/graph', #todo
            }
        
class Dot(cyclone.web.RequestHandler):
    def get(self):
        configGraph = self.settings.config.graph
        dot = dotrender.render(configGraph, self.settings.boards)
        self.write(dot)
        
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

        self.settings.board.outputStatements([stmt])

class Boards(cyclone.web.RequestHandler):
    def get(self):
        self.set_header('Content-type', 'application/json')
        self.write(json.dumps({
            'host': hostname,
            'boards': [self.settings.board.description()]
        }, indent=2))
        
def main():
    arg = docopt("""
    Usage: piNode.py [options]

    -v   Verbose
    """)
    log.setLevel(logging.WARN)
    if arg['-v']:
        from twisted.python import log as twlog
        twlog.startLogging(sys.stdout)

        log.setLevel(logging.DEBUG)

    masterGraph = PatchableGraph()
    config = Config(masterGraph)

    thisHost = Literal(hostname)
    for row in config.graph.query(
            'SELECT ?board WHERE { ?board a :PiBoard; :hostname ?h }',
            initBindings=dict(h=thisHost)):
        thisBoard = row.board
        break
    else:
        raise ValueError("config had no board for :hostname %r" % thisHost)

    log.info("found config for board %r" % thisBoard)
    board = Board(config.graph, masterGraph, thisBoard)
    board.startPolling()
    
    reactor.listenTCP(9059, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler, {
            "path": "../arduinoNode/static", "default_filename": "index.html"}),
        (r'/static/(.*)', cyclone.web.StaticFileHandler, {"path": "../arduinoNode/static"}),
        (r'/boards', Boards),
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        (r'/dot', Dot),
        ], config=config, board=board, debug=arg['-v']), interface='::')
    log.warn('serving on 9059')
    reactor.run()

main()
