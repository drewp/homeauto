from __future__ import division
import glob, sys, logging, subprocess, socket, os, hashlib, time, tempfile
import shutil, json, socket
import cyclone.web
from rdflib import Graph, Namespace, URIRef, Literal, RDF
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task
from docopt import docopt
logging.basicConfig(level=logging.DEBUG)
sys.path.append("/my/site/magma")
from stategraph import StateGraph
sys.path.append('/home/pi/dim/PIGPIO')
import pigpio

import devices

log = logging.getLogger()
logging.getLogger('serial').setLevel(logging.WARN)
ROOM = Namespace('http://projects.bigasterisk.com/room/')
HOST = Namespace('http://bigasterisk.com/ruler/host/')

hostname = socket.gethostname()

class GraphPage(cyclone.web.RequestHandler):
    def get(self):
        g = StateGraph(ctx=ROOM['pi/%s' % hostname])

        for stmt in self.settings.board.currentGraph():
            g.add(stmt)

        if self.get_argument('config', 'no') == 'yes':
            for stmt in self.settings.config.graph:
                g.add(stmt)
        
        self.set_header('Content-type', 'application/x-trig')
        self.write(g.asTrig())

class Board(object):
    """similar to arduinoNode.Board but without the communications stuff"""
    def __init__(self, graph, uri, onChange):
        self.graph, self.uri = graph, uri
        self.pi = pigpio.pi()
        self._devs = devices.makeDevices(graph, self.uri, self.pi)
        self._statementsFromInputs = {} # input device uri: latest statements

    def startPolling(self):
        task.LoopingCall(self._poll).start(.5)

    def _poll(self):
        for i in self._devs:
            self._statementsFromInputs[i.uri] = i.poll()
        
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
                log.info("success")
        if unused:
            log.warn("No devices cared about these statements:")
            for s in unused:
                log.warn(repr(s))
        
class OutputPage(cyclone.web.RequestHandler):
   
    def put(self):
        subj = URIRef(self.get_argument('s'))
        pred = URIRef(self.get_argument('p'))

        turtleLiteral = self.request.body
        try:
            obj = Literal(float(turtleLiteral))
        except TypeError:
            obj = Literal(turtleLiteral)

        stmt = (subj, pred, obj)
        self.settings.board.outputStatements([stmt])


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
    
    config = Config()

    def onChange():
        # notify reasoning
        pass

    thisBoard = URIRef('http://bigasterisk.com/homeauto/node2')
    
    board = Board(config.graph, thisBoard, onChange)
    
    reactor.listenTCP(9059, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler, {
            "path": "static", "default_filename": "index.html"}),
        (r'/static/(.*)', cyclone.web.StaticFileHandler, {"path": "static"}),
        (r"/graph", GraphPage),
        (r'/output', OutputPage),
        (r'/dot', Dot),
        ], config=config, board=board))
    reactor.run()

main()
