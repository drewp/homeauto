"""
depends on packages:
 arduino-mk
 indent
"""
from __future__ import division
import glob, sys, logging, subprocess, socket, os, hashlib, time, tempfile
import shutil, json
import serial
import cyclone.web
from rdflib import Graph, Namespace, URIRef, Literal, RDF, ConjunctiveGraph
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task
from docopt import docopt

import devices
import write_arduino_code
import dotrender
import rdflib_patch
rdflib_patch.fixQnameOfUriWithTrailingSlash()

logging.basicConfig(level=logging.DEBUG)

from loggingserial import LoggingSerial

sys.path.append("../../lib")
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler

sys.path.append("/my/proj/light9")
from light9.rdfdb.patch import Patch
from light9.rdfdb.rdflibpatch import inContext

sys.path.append("/my/proj/room")
from carbondata import CarbonClient

log = logging.getLogger()
logging.getLogger('serial').setLevel(logging.WARN)

ROOM = Namespace('http://projects.bigasterisk.com/room/')
HOST = Namespace('http://bigasterisk.com/ruler/host/')

ACTION_BASE = 10 # higher than any of the fixed command numbers

hostname = socket.gethostname()
CTX = ROOM['arduinosOn%s' % hostname]

class Config(object):
    def __init__(self, masterGraph):
        self.graph = ConjunctiveGraph()
        log.info('read config')
        for f in os.listdir('config'):
            if f.startswith('.'): continue
            self.graph.parse('config/%s' % f, format='n3')
        self.graph.bind('', ROOM) # not working
        self.graph.bind('rdf', RDF)
        # config graph is too noisy; maybe make it a separate resource
        #masterGraph.patch(Patch(addGraph=self.graph))

    def serialDevices(self):
        return dict([(row.dev, row.board) for row in self.graph.query(
            """SELECT ?board ?dev WHERE {
                 ?board :device ?dev;
                 a :ArduinoBoard .
               }""", initNs={'': ROOM})])
        
class Board(object):
    """an arduino connected to this computer"""
    baudrate = 115200
    def __init__(self, dev, configGraph, masterGraph, uri):
        """
        each connected thing has some pins.
        """
        self.uri = uri
        self.configGraph = configGraph
        self.masterGraph = masterGraph
        self.dev = dev

        self.masterGraph.patch(Patch(addQuads=self.staticStmts()))

        # The order of this list needs to be consistent between the
        # deployToArduino call and the poll call.
        self._devs = devices.makeDevices(configGraph, self.uri)
        self._devCommandNum = dict((dev.uri, ACTION_BASE + devIndex)
                                   for devIndex, dev in enumerate(self._devs))
        self._polledDevs = [d for d in self._devs if d.generatePollCode()]
        
        self._statementsFromInputs = {} # input device uri: latest statements
        self._carbon = CarbonClient(serverHost='bang')
        self.open()
        for d in self._devs:
            self.syncMasterGraphToHostStatements(d)

    def description(self):
        """for web page"""
        return {
            'uri': self.uri,
            'dev': self.dev,
            'baudrate': self.baudrate,
            'devices': [d.description() for d in self._devs],
            }
        
    def open(self):
        self.ser = LoggingSerial(port=self.dev, baudrate=self.baudrate,
                                 timeout=2)
        
    def startPolling(self):
        task.LoopingCall(self._poll).start(.5)
            
    def _poll(self):
        """
        even boards with no inputs need some polling to see if they're
        still ok
        """
        try:
            self._pollWork()
        except serial.SerialException:
            reactor.crash()
            raise
        except Exception as e:
            import traceback; traceback.print_exc()
            log.warn("poll: %r" % e)
            
    def _pollWork(self):
        t1 = time.time()
        self.ser.write("\x60\x00")
        for i in self._polledDevs:
            prev = self._statementsFromInputs.get(i.uri, [])
            new = self._statementsFromInputs[i.uri] = inContext(
                i.readFromPoll(self.ser.read), i.uri)
            self.masterGraph.patch(Patch.fromDiff(prev, new))
            
        #plus statements about succeeding or erroring on the last poll
        byte = self.ser.read(1)
        if byte != 'x':
            raise ValueError("after poll, got %x instead of 'x'" % byte)
        elapsed = time.time() - t1
        if elapsed > 1.0:
            log.warn('poll took %.1f seconds' % elapsed)
        self._exportToGraphite()

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
        for s, graphiteName in self.configGraph.subject_objects(ROOM['graphiteName']):
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
                self.ser.write("\x60" + chr(self._devCommandNum[dev.uri]))
                dev.sendOutput(stmtsForDev, self.ser.write, self.ser.read)
                if self.ser.read(1) != 'k':
                    raise ValueError(
                        "%s sendOutput/generateActionCode didn't use "
                        "matching output bytes" % dev.__class__)
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

    def generateArduinoCode(self):
        code = write_arduino_code.writeCode(self.baudrate, self._devs,
                                            self._devCommandNum)
        code = write_arduino_code.indent(code)
        cksum = hashlib.sha1(code).hexdigest()
        code = code.replace('CODE_CHECKSUM', cksum)
        return code, cksum

    def _readBoardChecksum(self, length):
        # this is likely right after reset, so it might take 2 seconds
        for tries in range(6):
            self.ser.write("\x60\x01")
            try:
                return self.ser.read(length)
            except ValueError:
                if tries == 5:
                    raise
            time.sleep(.5)
        raise ValueError

    def _boardIsCurrent(self, currentChecksum):
        try:
            boardCksum = self._readBoardChecksum(len(currentChecksum))
            if boardCksum == currentChecksum:
                log.info("board has current code (%s)" % currentChecksum)
                return True
            else:
                log.info("board responds with incorrect code version")
        except Exception as e:
            log.info("can't get code version from board: %r" % e)
        return False
        
    def deployToArduino(self):
        code, cksum = self.generateArduinoCode()

        if self._boardIsCurrent(cksum):
            return
        
        try:
            if hasattr(self, 'ser'):
                self.ser.close()
            workDir = tempfile.mkdtemp(prefix='arduinoNode_board_deploy')
            try:
                self._arduinoMake(workDir, code)
            finally:
                shutil.rmtree(workDir)
        finally:
            self.open()

    def _arduinoMake(self, workDir, code):
        with open(workDir + '/makefile', 'w') as makefile:
            makefile.write(write_arduino_code.writeMakefile(
                dev=self.dev,
                tag=self.configGraph.value(self.uri, ROOM['boardTag']),
                allLibs=sum((d.generateArduinoLibs() for d in self._devs), [])))

        with open(workDir + '/main.ino', 'w') as main:
            main.write(code)

        subprocess.check_call(['make', 'upload'], cwd=workDir)
        

    def currentGraph(self):
        g = Graph()
        

        for dev in self._devs:
            for stmt in dev.hostStatements():
                g.add(stmt)
        return g

class Dot(cyclone.web.RequestHandler):
    def get(self):
        configGraph = self.settings.config.graph
        dot = dotrender.render(configGraph, self.settings.boards)
        self.write(dot)
        
class ArduinoCode(cyclone.web.RequestHandler):
    def get(self):
        board = [b for b in self.settings.boards if
                 b.uri == URIRef(self.get_argument('board'))][0]
        self.set_header('Content-Type', 'text/plain')
        code, cksum = board.generateArduinoCode()
        self.write(code)

def rdfGraphBody(body, headers):
    g = Graph()
    g.parse(StringInputSource(body), format='nt')
    return g

class OutputPage(cyclone.web.RequestHandler):
    def post(self):
        # for old ui; use PUT instead
        stmts = list(rdfGraphBody(self.request.body, self.request.headers))
        for b in self.settings.boards:
            b.outputStatements(stmts)
            
    def put(self):
        subj = URIRef(self.get_argument('s'))
        pred = URIRef(self.get_argument('p'))

        turtleLiteral = self.request.body
        try:
            obj = Literal(float(turtleLiteral))
        except ValueError:
            obj = Literal(turtleLiteral)

        stmt = (subj, pred, obj)
        for b in self.settings.boards:
            b.outputStatements([stmt])
        
        
class Boards(cyclone.web.RequestHandler):
    def get(self):
        self.set_header('Content-type', 'application/json')
        self.write(json.dumps({
            'host': hostname,
            'boards': [b.description() for b in self.settings.boards]
        }, indent=2))
            
def currentSerialDevices():
    log.info('find connected boards')
    return glob.glob('/dev/serial/by-id/*')
        
def main():
    arg = docopt("""
    Usage: arduinoNode.py [options]

    -v   Verbose
    """)
    log.setLevel(logging.WARN)
    if arg['-v']:
        from twisted.python import log as twlog
        twlog.startLogging(sys.stdout)

        log.setLevel(logging.DEBUG)

    masterGraph = PatchableGraph()
    config = Config(masterGraph)
    current = currentSerialDevices()

    boards = []
    for dev, board in config.serialDevices().items():
        if str(dev) not in current:
            continue
        log.info("we have board %s connected at %s" % (board, dev))
        b = Board(dev, config.graph, masterGraph, board)
        boards.append(b)

    for b in boards:
        b.deployToArduino()

    log.info('open boards')
    for b in boards:
        b.startPolling()


    reactor.listenTCP(9059, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler, {
            "path": "static", "default_filename": "index.html"}),
        (r'/static/(.*)', cyclone.web.StaticFileHandler, {"path": "static"}),
        (r'/boards', Boards),
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        (r'/arduinoCode', ArduinoCode),
        (r'/dot', Dot),
        ], config=config, boards=boards), interface='::')
    reactor.run()

main()
