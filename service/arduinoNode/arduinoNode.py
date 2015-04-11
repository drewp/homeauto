"""
depends on arduino-mk
"""
import shutil
import tempfile
import glob, sys, logging, subprocess, socket, os, hashlib, time
import cyclone.web
from rdflib import Graph, Namespace, URIRef, Literal, RDF
from twisted.internet import reactor, task
import devices
import dotrender

logging.basicConfig(level=logging.DEBUG)

from loggingserial import LoggingSerial

sys.path.append("/my/site/magma")
from stategraph import StateGraph

log = logging.getLogger()
logging.getLogger('serial').setLevel(logging.WARN)

import rdflib.namespace
old_split = rdflib.namespace.split_uri
def new_split(uri):
    try:
        return old_split(uri)
    except Exception:
        return uri, ''
rdflib.namespace.split_uri = new_split

ROOM = Namespace('http://projects.bigasterisk.com/room/')
HOST = Namespace('http://bigasterisk.com/ruler/host/')

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
        self._polledDevs = [d for d in self._devs if d.generatePollCode()]
        
        self._statementsFromInputs = {} # input uri: latest statements

        self.open()

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
        except Exception as e:
            log.warn("poll: %r" % e)
            
    def _pollWork(self):
        self.ser.write("\x60\x00")
        for i in self._polledDevs:
            self._statementsFromInputs[i.uri] = i.readFromPoll(self.ser.read)
        #plus statements about succeeding or erroring on the last poll

    def currentGraph(self):
        g = Graph()
        
        g.add((HOST[socket.gethostname()], ROOM['connectedTo'], self.uri))

        for si in self._statementsFromInputs.values():
            for s in si:
                g.add(s)
        return g
            
    def generateArduinoCode(self):
        generated = {
            'baudrate': self.baudrate,
            'includes': '',
            'global': '',
            'setups': '',
            'polls': ''
        }
        for attr in ['includes', 'global', 'setups', 'polls']:
            for i in self._devs:
                if attr == 'includes':
                    gen = '\n'.join('#include "%s"\n' % inc
                                    for inc in i.generateIncludes())
                elif attr == 'global': gen = i.generateGlobalCode()
                elif attr == 'setups': gen = i.generateSetupCode()
                elif attr == 'polls': gen = i.generatePollCode()
                else: raise NotImplementedError
                    
                if gen:
                    generated[attr] += '// for %s\n%s\n' % (i.uri, gen)

        return '''
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
        if (cmd == 0x00) {
%(polls)s;
        } else if (cmd == 0x01) {
          Serial.write("CODE_CHECKSUM");
        }
    }
}
        ''' % generated


    def codeChecksum(self, code):
        # this is run on the code without CODE_CHECKSUM replaced yet
        return hashlib.sha1(code).hexdigest()

    def readBoardChecksum(self, length):
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

    def boardIsCurrent(self, currentChecksum):
        try:
            boardCksum = self.readBoardChecksum(len(currentChecksum))
            if boardCksum == currentChecksum:
                log.info("board has current code (%s)" % currentChecksum)
                return True
            else:
                log.info("board responds with incorrect code version")
        except Exception as e:
            log.info("can't get code version from board: %r" % e)
        return False
        
    def deployToArduino(self):
        code = self.generateArduinoCode()
        cksum = self.codeChecksum(code)
        code = code.replace('CODE_CHECKSUM', cksum)

        if self.boardIsCurrent(cksum):
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
        

class Index(cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/html")
        self.write(open("index.html").read())
        
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
        self.write(board.generateArduinoCode())
        
        
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
        (r"/", Index),
        (r"/graph", GraphPage),
        (r'/arduinoCode', ArduinoCode),
        (r'/dot', Dot),
        ], config=config, boards=boards))
    reactor.run()

main()
