from __future__ import division
import sys, logging, socket, json, time, pkg_resources
import cyclone.web
from cyclone.httpclient import fetch
from rdflib import Namespace, URIRef, Literal, Graph, RDF, ConjunctiveGraph
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task
from twisted.internet.threads import deferToThread
from docopt import docopt
import etcd3
from greplin import scales
from greplin.scales.cyclonehandler import StatsHandler

logging.basicConfig(level=logging.DEBUG)

sys.path.append("../../lib")
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler

from rdfdb.rdflibpatch import inContext
from rdfdb.patch import Patch

try:
    import pigpio
except ImportError:
    class pigpio(object):
        @staticmethod
        def pi():
            return None

import devices
from export_to_influxdb import InfluxExporter

log = logging.getLogger()
logging.getLogger('serial').setLevel(logging.WARN)

ROOM = Namespace('http://projects.bigasterisk.com/room/')
HOST = Namespace('http://bigasterisk.com/ruler/host/')

hostname = socket.gethostname()
CTX = ROOM['pi/%s' % hostname]

STATS = scales.collection('/root',
                          scales.PmfStat('configReread'),
                          scales.IntStat('pollException'),
                          scales.PmfStat('boardPoll'),
                          scales.PmfStat('sendOneshot'),
                          scales.PmfStat('outputStatements'),

)
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
    def __init__(self, masterGraph, hubHost):
        self.etcd = etcd3.client(host=hubHost, port=9022)

        self.masterGraph = masterGraph
        self.hubHost = hubHost
        self.configGraph = ConjunctiveGraph()
        self.boards = []
        self.etcPrefix = 'pi/'

        self.reread()

        deferToThread(self.watchEtcd)

    def watchEtcd(self):
        events, cancel = self.etcd.watch_prefix(self.etcPrefix)
        reactor.addSystemEventTrigger('before', 'shutdown', cancel)
        for ev in events:
            log.info('%s changed', ev.key)
            reactor.callFromThread(self.configChanged)

    def configChanged(self):
        self.cancelRead()
        self.rereadLater = reactor.callLater(.1, self.reread)

    def cancelRead(self):
        if getattr(self, 'rereadLater', None):
            self.rereadLater.cancel()
        self.rereadLater = None

    @STATS.configReread.time()
    def reread(self):
        self.rereadLater = None
        log.info('read config')
        self.configGraph = ConjunctiveGraph()
        for v, md in self.etcd.get_prefix(self.etcPrefix):
            log.info('  read file %r', md.key)
            self.configGraph.parse(StringInputSource(v), format='n3')
        self.configGraph.bind('', ROOM)
        self.configGraph.bind('rdf', RDF)
        # config graph is too noisy; maybe make it a separate resource
        #masterGraph.patch(Patch(addGraph=self.configGraph))
        self.setupBoards()
        
    def setupBoards(self):       
        thisHost = Literal(hostname)
        for row in self.configGraph.query(
                'SELECT ?board WHERE { ?board a :PiBoard; :hostname ?h }',
                initBindings=dict(h=thisHost)):
            thisBoard = row.board
            break
        else:
            log.warn("config had no board for :hostname %s. Waiting for config update." %
                     thisHost)
            self.boards = []
            return

        log.info("found config for board %r" % thisBoard)
        self.boards = [Board(self.configGraph, self.masterGraph, thisBoard, self.hubHost)]
        self.boards[0].startPolling()


class Board(object):
    """similar to arduinoNode.Board but without the communications stuff"""
    def __init__(self, graph, masterGraph, uri, hubHost):
        self.graph, self.uri = graph, uri
        self.hubHost = hubHost
        self.masterGraph = masterGraph
        self.masterGraph.setToGraph(self.staticStmts())
        self.pi = pigpio.pi()
        self._devs = devices.makeDevices(graph, self.uri, self.pi)
        log.debug('found %s devices', len(self._devs))
        self._statementsFromInputs = {} # input device uri: latest statements
        self._lastPollTime = {} # input device uri: time()
        self._influx = InfluxExporter(self.graph)
        for d in self._devs:
            self.syncMasterGraphToHostStatements(d)
            
    def startPolling(self):
        task.LoopingCall(self._poll).start(.05)

    @STATS.boardPoll.time() # not differentiating multiple boards here
    def _poll(self):
        try:
            self._pollMaybeError()
        except Exception:
            STATS.pollException += 1
            log.exception("During poll:")
            
    def _pollMaybeError(self):
        pollTime = {} # uri: sec
        for i in self._devs:
            now = time.time()
            if (hasattr(i, 'pollPeriod') and
                self._lastPollTime.get(i.uri, 0) + i.pollPeriod > now):
                continue
            #need something like:
            #  with i.pollTiming.time():
            new = i.poll()
            pollTime[i.uri] = time.time() - now
            if isinstance(new, dict): # new style
                oneshot = new['oneshot']
                new = new['latest']
            else:
                oneshot = None

            self._updateMasterWithNewPollStatements(i.uri, new)

            if oneshot:
                self._sendOneshot(oneshot)
            self._lastPollTime[i.uri] = now
        if log.isEnabledFor(logging.DEBUG):
            log.debug('poll times:')
            for u, s in sorted(pollTime.items()):
                log.debug("  %.4f ms %s", s * 1000, u)
            log.debug('total poll time: %f ms', sum(pollTime.values()) * 1000)
            
        pollResults = map(set, self._statementsFromInputs.values())
        if pollResults:
            self._influx.exportToInflux(set.union(*pollResults))

    def _updateMasterWithNewPollStatements(self, dev, new):
        prev = self._statementsFromInputs.get(dev, set())

        # it's important that quads from different devices
        # don't clash, since that can lead to inconsistent
        # patches (e.g.
        #   dev1 changes value from 1 to 2;
        #   dev2 changes value from 2 to 3;
        #   dev1 changes from 2 to 4 but this patch will
        #     fail since the '2' statement is gone)
        self.masterGraph.patch(Patch.fromDiff(inContext(prev, dev),
                                              inContext(new, dev)))
        self._statementsFromInputs[dev] = new

    @STATS.sendOneshot.time()
    def _sendOneshot(self, oneshot):
        body = (' '.join('%s %s %s .' % (s.n3(), p.n3(), o.n3())
                         for s,p,o in oneshot)).encode('utf8')
        url = 'http://%s:9071/oneShot' % self.hubHost
        d = fetch(method='POST',
                  url=url,
                  headers={'Content-Type': ['text/n3']},
                  postdata=body,
                  timeout=5)
        def err(e):
            log.info('oneshot post to %r failed:  %s',
                     url, e.getErrorMessage())
        d.addErrback(err)

    @STATS.outputStatements.time()
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
        configGraph = self.settings.config.configGraph
        dot = dotrender.render(configGraph, self.settings.config.boards)
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

        for b in self.settings.config.boards:
            b.outputStatements([stmt])

class Boards(cyclone.web.RequestHandler):
    def get(self):
        self.set_header('Content-type', 'application/json')
        self.write(json.dumps({
            'host': hostname,
            'boards': [b.description() for b in self.settings.config.boards]
        }, indent=2))
        
def main():
    arg = docopt("""
    Usage: piNode.py [options]

    -v           Verbose
    --ow         Just report onewire device URIs and readings, then exit.
    --hub=HOST   Hostname for etc3 and oneshot posts. [default: bang.vpn-home.bigasterisk.com]
    """)
    log.setLevel(logging.WARN)
    if arg['-v']:
        from twisted.python import log as twlog
        twlog.startLogging(sys.stdout)

        log.setLevel(logging.DEBUG)

    if arg['--ow']:
        log.setLevel(logging.INFO)
        for stmt in devices.OneWire().poll():
            print stmt
        return
        
    masterGraph = PatchableGraph()
    config = Config(masterGraph, arg['--hub'])
    
    static = pkg_resources.resource_filename('homeauto_anynode', 'static/')

    reactor.listenTCP(9059, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler, {
            "path": static, "default_filename": "index.html"}),
        (r'/static/(.*)', cyclone.web.StaticFileHandler, {"path": static}),
        (r'/stats/(.*)', StatsHandler, {'serverName': 'piNode'}),
        (r'/boards', Boards),
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        (r'/dot', Dot),
    ], config=config, debug=arg['-v']), interface='::')
    log.warn('serving on 9059')
    reactor.run()

main()
