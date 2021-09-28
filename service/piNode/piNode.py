import logging, socket, json, time, pkg_resources
import cyclone.web
from rdflib import Namespace, URIRef, Literal, Graph, RDF, ConjunctiveGraph
from rdflib.parser import StringInputSource
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, maybeDeferred, returnValue
from twisted.internet.threads import deferToThread
from docopt import docopt
import etcd3
from greplin import scales
from greplin.scales.cyclonehandler import StatsHandler
import os
#os.environ['PIGPIO_ADDR'] = 'pigpio' # (aka the docker host)
import pigpio
import treq

from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from cycloneerr import PrettyErrorHandler
from standardservice.logsetup import log, verboseLogging
from rdfdb.rdflibpatch import inContext
from rdfdb.patch import Patch
from rdflib_pi_opt import patchRandid
from export_to_influxdb import InfluxExporter

import devices

ROOM = Namespace('http://projects.bigasterisk.com/room/')
HOST = Namespace('http://bigasterisk.com/ruler/host/')

hostname = socket.gethostname()
CTX = ROOM['pi/%s' % hostname]

STATS = scales.collection('/root',
                          scales.PmfStat('configReread'),
                          scales.IntStat('pollException'),
                          scales.PmfStat('pollAll'),
                          scales.PmfStat('sendOneshot'),
                          scales.PmfStat('outputStatements'),
                          scales.IntStat('oneshotSuccess'),
                          scales.IntStat('oneshotFail'),
)

class Config(object):
    def __init__(self, masterGraph):
        log.info('connect to etcd-homeauto')
        self.etcd = etcd3.client(host='etcd-homeauto', port=9022)
        log.info('version %r', self.etcd.status().version)


        self.masterGraph = masterGraph
        self.configGraph = ConjunctiveGraph()
        self.boards = []
        self.etcPrefix = 'pi/'
        self.rereadLater = None

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
        if self.rereadLater:
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
        self.boards = [Board(self.configGraph, self.masterGraph, thisBoard)]


class DeviceRunner(object):
    def __init__(self, dev, masterGraph, sendOneshot, influx):
        self.dev = dev
        self.masterGraph = masterGraph
        self.sendOneshot = sendOneshot
        self.influx = influx
        self.period = getattr(self.dev, 'pollPeriod', .05)
        self.latestStatementsFromInputs = set()
        self.lastPollTime = None

        reactor.callLater(0, self.poll)

    def syncMasterGraphToHostStatements(self):
        hostStmtCtx = URIRef(self.dev.uri + '/host')
        newQuads = inContext(self.dev.hostStatements(), hostStmtCtx)
        p = self.masterGraph.patchSubgraph(hostStmtCtx, newQuads)
        if p:
            log.debug("patch master with these host stmts %s", p)

    @inlineCallbacks
    def poll(self):
        now = time.time()
        try:
            with self.dev.stats.poll.time():
                new = yield maybeDeferred(self.dev.poll)
        finally:
            reactor.callLater(max(0, self.period - (time.time() - now)), self.poll)

        if isinstance(new, dict): # new style
            oneshot = set(new['oneshot'])
            new = set(new['latest'])
        else:
            oneshot = set()
            new = set(new)

        prev = self.latestStatementsFromInputs
        # it's important that quads from different devices
        # don't clash, since that can lead to inconsistent
        # patches (e.g.
        #   dev1 changes value from 1 to 2;
        #   dev2 changes value from 2 to 3;
        #   dev1 changes from 2 to 4 but this patch will
        #     fail since the '2' statement is gone)
        self.masterGraph.patch(Patch.fromDiff(inContext(prev, self.dev.uri),
                                              inContext(new, self.dev.uri)))
        self.latestStatementsFromInputs = new

        self.syncMasterGraphToHostStatements() # needed?

        if oneshot:
            self.sendOneshot(oneshot)
        self.lastPollTime = now

        if self.latestStatementsFromInputs:
            self.influx.exportToInflux(set.union(set(self.latestStatementsFromInputs)))

        returnValue(new)

    def filterIncomingStatements(self, stmts):
        wanted = set()
        unwanted = set(stmts)
        for pat in self.dev.outputPatterns():
            if [term is None for term in pat] != [False, False, True]:
                raise NotImplementedError
            for stmt in stmts:
                if stmt[:2] == pat[:2]:
                    wanted.add(stmt)
                    unwanted.discard(stmt)
        return wanted, unwanted

    def onPutStatements(self, stmts):
        log.info("output goes to action handler for %s" % self.dev.uri)
        with self.dev.stats.output.time():
            self.dev.sendOutput(stmts)
        self.syncMasterGraphToHostStatements()

def sendOneshot(oneshot):
    body = (' '.join('%s %s %s .' % (s.n3(), p.n3(), o.n3())
                     for s,p,o in oneshot)).encode('utf8')
    url = 'http://reasoning:9071/oneShot'
    log.debug('post to %r', url)
    d = treq.post(
              url=url.encode('ascii'),
              headers={b'Content-Type': [b'text/n3']},
              data=body,
              timeout=5)

    def ok(k):
        log.debug('sendOneshot to %r success', url)
        STATS.oneshotSuccess += 1
    def err(e):
        log.info('oneshot post to %r failed:  %s',
                 url, e.getErrorMessage())
        STATS.oneshotFail += 1
    d.addCallbacks(ok, err)

class Board(object):
    """similar to arduinoNode.Board but without the communications stuff"""
    def __init__(self, graph, masterGraph, uri):
        self.graph, self.uri = graph, uri
        self.masterGraph = masterGraph

        self.masterGraph.setToGraph(self.staticStmts())
        self.pi = pigpio.pi()

        self._influx = InfluxExporter(self.graph)
        self._runners = [DeviceRunner(d, self.masterGraph, self.sendOneshot, self._influx)
                         for d in devices.makeDevices(graph, self.uri, self.pi)]
        log.debug('found %s devices', len(self._runners))

    @STATS.sendOneshot.time()
    def sendOneshot(self, oneshot):
        sendOneshot(oneshot)

    @STATS.outputStatements.time()
    def outputStatements(self, stmts: set):
        if not stmts:
            return
        for devRunner in self._runners:
            wanted, unwanted = devRunner.filterIncomingStatements(stmts)
            log.info(f'\ndev {devRunner.dev.uri}:n wanted {wanted}. unwanted {unwanted}')
            if len(wanted) == len(stmts):
                devRunner.onPutStatements(stmts)
                break
            elif len(unwanted) == len(stmts):
                continue
            else:
                raise NotImplementedError(f'dev {devRunner.dev.uri} wanted only {wanted}')
        else:
            log.info("Board %s doesn't care about these statements:", self.uri)
            for s in unwanted:
                log.warn("%r", s)

    def staticStmts(self):
        return [(HOST[hostname], ROOM['connectedTo'], self.uri, CTX)]

    def description(self):
        """for web page"""
        return {
            'uri': self.uri,
            'devices': [d.dev.description() for d in self._runners],
            'graph': 'http://sticker:9059/graph', #todo
        }

def rdfGraphBody(body, headers):
    g = Graph()
    g.parse(StringInputSource(body), format='nt')
    return g

class OutputPage(PrettyErrorHandler, cyclone.web.RequestHandler):
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
            stmt = next(g.triples((None, None, None)))

        for b in self.settings.config.boards:
            b.outputStatements({stmt})

class Boards(PrettyErrorHandler, cyclone.web.RequestHandler):
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
    """)
    verboseLogging(arg['-v'])

    if arg['--ow']:
        log.setLevel(logging.INFO)
        for stmt in devices.OneWire().poll():
            print(stmt)
        return

    patchRandid()

    masterGraph = PatchableGraph()
    config = Config(masterGraph)

    static = pkg_resources.resource_filename('homeauto_anynode', 'static/')

    reactor.listenTCP(9059, cyclone.web.Application([
        (r"/(|output-widgets.html)", cyclone.web.StaticFileHandler, {
            "path": static, "default_filename": "index.html"}),
        (r'/static/(.*)', cyclone.web.StaticFileHandler, {"path": static}),
        (r'/stats/(.*)', StatsHandler, {'serverName': 'piNode'}),
        (r'/boards', Boards),
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
    ], config=config, debug=arg['-v']), interface='::')
    log.warn('serving on 9059')
    reactor.run()

if __name__ == '__main__':
    main()
