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
from rdflib import Graph, Namespace, URIRef, Literal, RDF
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task

import devices
import dotrender
import rdflib_patch
rdflib_patch.fixQnameOfUriWithTrailingSlash()

logging.basicConfig(level=logging.DEBUG)

from loggingserial import LoggingSerial

sys.path.append("/my/site/magma")
from stategraph import StateGraph

log = logging.getLogger()
logging.getLogger('serial').setLevel(logging.WARN)

ROOM = Namespace('http://projects.bigasterisk.com/room/')
HOST = Namespace('http://bigasterisk.com/ruler/host/')

ACTION_BASE = 10 # higher than any of the fixed command numbers

class Config(object):
    def __init__(self):
        self.graph = Graph()
        log.info('read config')
        self.graph.parse('config.n3', format='n3')
        self.graph.bind('', ROOM) # not working
        self.graph.bind('rdf', RDF)

    def serialDevices(self):
        return dict([(row.dev, row.board) for row in self.graph.query(
            """SELECT ?board ?dev WHERE {
                 ?board :device ?dev;
                 a :ArduinoBoard .
               }""", initNs={'': ROOM})])
        
class Board(object):
    """an arduino connected to this computer"""
    baudrate = 115200
    def __init__(self, dev, graph, uri, onChange):
        """
        each connected thing has some pins.

        We'll call onChange when we know the currentGraph() has
        changed (and not just in creation time).
        """
        self.uri = uri
        self.graph = graph
        self.dev = dev
        
        # The order of this list needs to be consistent between the
        # deployToArduino call and the poll call.
        self._devs = devices.makeDevices(graph, self.uri)
        self._devCommandNum = dict((dev.uri, ACTION_BASE + devIndex)
                                   for devIndex, dev in enumerate(self._devs))
        self._polledDevs = [d for d in self._devs if d.generatePollCode()]
        
        self._statementsFromInputs = {} # input uri: latest statements

        self.open()

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
            log.warn("poll: %r" % e)
            
    def _pollWork(self):
        t1 = time.time()
        self.ser.write("\x60\x00")
        for i in self._polledDevs:
            self._statementsFromInputs[i.uri] = i.readFromPoll(self.ser.read)
        #plus statements about succeeding or erroring on the last poll
        byte = self.ser.read(1)
        if byte != 'x':
            raise ValueError("after poll, got %x instead of 'x'" % byte)
        elapsed = time.time() - t1
        if elapsed > 1.0:
            log.warn('poll took %.1f seconds' % elapsed)
        

    def currentGraph(self):
        g = Graph()
        
        g.add((HOST[socket.gethostname()], ROOM['connectedTo'], self.uri))

        for si in self._statementsFromInputs.values():
            for s in si:
                g.add(s)
        return g

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
                log.info("success")
        if unused:
            log.warn("No devices cared about these statements:")
            for s in unused:
                log.warn(repr(s))
        
    def generateArduinoCode(self):
        generated = {
            'baudrate': self.baudrate,
            'includes': '',
            'global': '',
            'setups': '',
            'polls': '',
            'actions': '',            
        }
        for attr in ['includes', 'global', 'setups', 'polls', 'actions']:
            for dev in self._devs:
                if attr == 'includes':
                    gen = '\n'.join('#include "%s"\n' % inc
                                    for inc in dev.generateIncludes())
                elif attr == 'global': gen = dev.generateGlobalCode()
                elif attr == 'setups': gen = dev.generateSetupCode()
                elif attr == 'polls': gen = dev.generatePollCode()
                elif attr == 'actions':
                    code = dev.generateActionCode()
                    if code:
                        gen = '''else if (cmd == %(cmdNum)s) {
                                   %(code)s
                                   Serial.write('k');
                                 }
                              ''' % dict(cmdNum=self._devCommandNum[dev.uri],
                                         code=code)
                    else:
                        gen = ''
                else:
                    raise NotImplementedError
                    
                if gen:
                    generated[attr] += '// for %s\n%s\n' % (dev.uri, gen)

        code = '''
%(includes)s

%(global)s
        
void setup() {
    Serial.begin(%(baudrate)d);
    Serial.flush();
    %(setups)s
}
        
void loop() {
    byte head, cmd;
    if (Serial.available() >= 2) {
        head = Serial.read();
        if (head != 0x60) {
            Serial.flush();
            return;
        }
        cmd = Serial.read();
        if (cmd == 0x00) { // poll
          %(polls)s
          Serial.write('x');
        } else if (cmd == 0x01) { // get code checksum
          Serial.write("CODE_CHECKSUM");
        }
        %(actions)s
    }
}
        ''' % generated
        try:
            with tempfile.SpooledTemporaryFile() as codeFile:
                codeFile.write(code)
                codeFile.seek(0)
                code = subprocess.check_output([
                    'indent',
                    '-linux',
                    '-fc1', # ok to indent comments
                    '-i4', # 4-space indent
                    '-sob' # swallow blanks (not working)
                ], stdin=codeFile)
        except OSError as e:
            log.warn("indent failed (%r)", e)
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
            makefile.write('''
BOARD_TAG = %(tag)s
USER_LIB_PATH := %(libs)s
ARDUINO_LIBS = %(arduinoLibs)s
MONITOR_PORT = %(dev)s

include /usr/share/arduino/Arduino.mk
            ''' % {
                'dev': self.dev,
                'tag': self.graph.value(self.uri, ROOM['boardTag']),
                'libs': os.path.abspath('arduino-libraries'),
                'arduinoLibs': ' '.join(sum((d.generateArduinoLibs()
                                             for d in self._devs), [])),
               })

        with open(workDir + '/main.ino', 'w') as main:
            main.write(code)

        subprocess.check_call(['make', 'upload'], cwd=workDir)
        
        
class GraphPage(cyclone.web.RequestHandler):
    def get(self):
        g = StateGraph(ctx=ROOM['arduinosOn%s' % 'host'])

        for b in self.settings.boards:
            for stmt in b.currentGraph():
                g.add(stmt)

        if self.get_argument('config', 'no') == 'yes':
            for stmt in self.settings.config.graph:
                g.add(stmt)
        
        self.set_header('Content-type', 'application/x-trig')
        self.write(g.asTrig())

class Dot(cyclone.web.RequestHandler):
    def get(self):
        configGraph = self.settings.config.graph
        dot = dotrender.render(configGraph, self.settings.boards)
        self.write(dot)
        
class ArduinoCode(cyclone.web.RequestHandler):
    def get(self):
        board = [b for b in self.settings.boards if
                 b.uri == URIRef(self.get_argument('board'))][0]
        self.set_header('Content-type', 'text/plain')
        code, cksum = board.generateArduinoCode()
        self.write(code)

def rdfGraphBody(body, headers):
    g = Graph()
    g.parse(StringInputSource(body), format='nt')
    return g
        
class OutputPage(cyclone.web.RequestHandler):
    def post(self):
        stmts = list(rdfGraphBody(self.request.body, self.request.headers))
        for b in self.settings.boards:
            b.outputStatements(stmts)

class Boards(cyclone.web.RequestHandler):
    def get(self):
        
        self.set_header('Content-type', 'application/json')
        self.write(json.dumps({
            'boards': [b.description() for b in self.settings.boards]
        }, indent=2))
            
def currentSerialDevices():
    log.info('find connected boards')
    return glob.glob('/dev/serial/by-id/*')

def main():
    config = Config()
    current = currentSerialDevices()

    def onChange():
        # notify reasoning
        pass
    
    boards = []
    for dev, board in config.serialDevices().items():
        if str(dev) not in current:
            continue
        log.info("we have board %s connected at %s" % (board, dev))
        b = Board(dev, config.graph, board, onChange)
        boards.append(b)

    boards[0].deployToArduino()

    log.info('open boards')
    for b in boards:
        b.startPolling()
        
    from twisted.python import log as twlog
    twlog.startLogging(sys.stdout)

    log.setLevel(logging.DEBUG)
    reactor.listenTCP(9059, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler, {
            "path": "static", "default_filename": "index.html"}),
        (r'/static/(.*)', cyclone.web.StaticFileHandler, {"path": "static"}),
        (r'/boards', Boards),
        (r"/graph", GraphPage),
        (r'/output', OutputPage),
        (r'/arduinoCode', ArduinoCode),
        (r'/dot', Dot),
        ], config=config, boards=boards))
    reactor.run()

main()
