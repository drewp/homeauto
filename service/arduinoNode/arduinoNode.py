import shutil
import tempfile
import glob, sys, logging, subprocess
import cyclone.web
from rdflib import Graph, Namespace, URIRef, Literal, RDF
from twisted.internet import reactor, task
import devices

logging.basicConfig(level=logging.DEBUG)

from loggingserial import LoggingSerial

sys.path.append("/my/site/magma")
from stategraph import StateGraph

log = logging.getLogger()
logging.getLogger('serial').setLevel(logging.WARN)


ROOM = Namespace('http://projects.bigasterisk.com/room/')

class Config(object):
    def __init__(self):
        self.graph = Graph()
        log.info('read config')
        self.graph.bind('', ROOM)
        self.graph.bind('rdf', RDF)
        self.graph.parse('config.n3', format='n3')

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
        self._inputs = [devices.PingInput(graph, self.uri)]
        for row in graph.query("""SELECT ?dev WHERE {
                                    ?board :hasPin ?pin .
                                    ?pin :connectedTo ?dev .
                                  } ORDER BY ?dev""",
                               initBindings=dict(board=self.uri),
                               initNs={'': ROOM}):
            self._inputs.append(devices.makeBoardInput(graph, row.dev))
        
        self._statementsFromInputs = {} # input uri: latest statements
        

    def open(self):
        self.ser = LoggingSerial(port=self.dev, baudrate=self.baudrate, timeout=2)
        
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
        for i in self._inputs:
            self._statementsFromInputs[i.uri] = i.readFromPoll(self.ser.read)
        #plus statements about succeeding or erroring on the last poll

    def currentGraph(self):
        g = Graph()
        for si in self._statementsFromInputs.values():
            for s in si:
                g.add(s)
        return g
            
    def generateArduinoCode(self):
        generated = {'baudrate': self.baudrate, 'setups': '', 'polls': ''}
        for attr in ['setups', 'polls']:
            for i in self._inputs:
                gen = (i.generateSetupCode() if attr == 'setups'
                       else i.generatePollCode())
                generated[attr] += '// for %s\n%s\n' % (i.uri, gen)

        return '''
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
        }
    }
}
        ''' % generated

    def deployToArduino(self):
        code = self.generateArduinoCode()
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
USER_LIB_PATH := 
ARDUINO_LIBS = 
MONITOR_PORT = %(dev)s

include /usr/share/arduino/Arduino.mk
            ''' % {
                'dev': self.dev,
                'tag': self.graph.value(self.uri, ROOM['boardTag']),
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
        nodes = {} # uri: nodeline
        edges = []

        serial = [0]
        def addNode(node):
            if node not in nodes or isinstance(node, Literal):
                id = 'node%s' % serial[0]
                if isinstance(node, URIRef):
                    short = self.settings.config.graph.qname(node)
                else:
                    short = str(node)
                nodes[node] = (
                    id,
                    '%s [ label="%s", shape = record, color = blue ];' % (
                    id, short))
                serial[0] += 1
            else:
                id = nodes[node][0]
            return id
        def addStmt(stmt):
            ns = addNode(stmt[0])
            no = addNode(stmt[2])
            edges.append('%s -> %s [ label="%s" ];' % (ns, no, stmt[1]))
        for b in self.settings.boards:
            for stmt in b.currentGraph():
                # color these differently from config ones
                addStmt(stmt)
        for stmt in self.settings.config.graph:
            addStmt(stmt)

        nodes = '\n'.join(line for _, line in nodes.values())
        edges = '\n'.join(edges)
        dot = '''
        digraph {
	rankdir = TB;
	charset="utf-8";
        %(nodes)s
        %(edges)s
        }
        ''' % dict(nodes=nodes, edges=edges)
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

    #boards[0].deployToArduino()

    log.info('open boards')
    for b in boards:
        b.open()
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
