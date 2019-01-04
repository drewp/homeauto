from docopt import docopt
from rdfdb.patch import Patch
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task
import cyclone.web
from cyclone.httpclient import fetch
import logging, time
from MFRC522.SimpleMFRC522 import SimpleMFRC522
from logsetup import log, enableTwistedLog

ROOM = Namespace('http://projects.bigasterisk.com/room/')

ctx = ROOM['frontDoorWindowRfidCtx']

def rdfGraphBody(body, headers):
    g = Graph()
    g.parse(StringInputSource(body), format='nt')
    return g

class OutputPage(cyclone.web.RequestHandler):
    def put(self):
        user = URIRef(self.request.headers['x-foaf-agent'])
        arg = self.request.arguments
        if arg.get('s') and arg.get('p'):
            subj = URIRef(arg['s'][-1])
            pred = URIRef(arg['p'][-1])
            obj = URIRef(self.request.body)
            stmt = (subj, pred, obj)
        else:
            g = rdfGraphBody(self.request.body, self.request.headers)
            assert len(g) == 1, len(g)
            stmt = g.triples((None, None, None)).next()
        self._onStatement(user, stmt)
    post = put
    
    def _onStatement(self, user, stmt):
        # write rfid to new key, etc.
        if stmt[1] == ROOM['keyContents']:
            return
        log.warn("ignoring %s", stmt)

sensor = ROOM['frontDoorWindowRfid']

class ReadLoop(object):
    def __init__(self, reader, masterGraph):
        self.reader = reader
        self.masterGraph = masterGraph
        self.log = {} # cardIdUri : most recent seentime

        self.pollPeriodSecs = .2
        self.expireSecs = 2
        
        task.LoopingCall(self.poll).start(self.pollPeriodSecs)
        
    def poll(self):
        now = time.time()

        self.flushOldReads(now)

        card_id, text = self.reader.read()
        if card_id is None:
            return

        cardIdUri = URIRef('http://bigasterisk.com/rfidCard/%s' % card_id)
        textLit = Literal(text.rstrip())

        is_new = cardIdUri not in self.log
        self.log[cardIdUri] = now
        if is_new:
            self.startCardRead(cardIdUri, textLit)
        
    def flushOldReads(self, now):
        for uri in self.log.keys():
            if self.log[uri] < now - self.expireSecs:
                self.endCardRead(uri)
                del self.log[uri]

    def startCardRead(self, cardUri, text):
        p = Patch(addQuads=[(sensor, ROOM['reading'], cardUri, ctx),
                            (cardUri, ROOM['cardText'], text, ctx)], delQuads=[])
        self.masterGraph.patch(p)
        self._sendOneshot([(sensor, ROOM['startReading'], cardUri),
                            (cardUri, ROOM['cardText'], text)])

    def endCardRead(self, cardUri):
        delQuads = []
        for spo in self.masterGraph._graph.triples((sensor, ROOM['reading'], cardUri)):
            delQuads.append(spo + (ctx,))
        for spo in self.masterGraph._graph.triples((cardUri, ROOM['cardText'], None)):
            delQuads.append(spo + (ctx,))
            
        self.masterGraph.patch(Patch(addQuads=[], delQuads=delQuads))
        
    def _sendOneshot(self, oneshot):
        body = (' '.join('%s %s %s .' % (s.n3(), p.n3(), o.n3())
                         for s,p,o in oneshot)).encode('utf8')
        url = 'http://bang6:9071/oneShot'
        d = fetch(method='POST',
                  url=url,
                  headers={'Content-Type': ['text/n3']},
                  postdata=body,
                  timeout=5)
        def err(e):
            log.info('oneshot post to %r failed:  %s',
                     url, e.getErrorMessage())
        d.addErrback(err)

                                                              
        
if __name__ == '__main__':
    arg = docopt("""
    Usage: rfid.py [options]

    -v   Verbose
    """)
    log.setLevel(logging.INFO)
    if arg['-v']:
        enableTwistedLog()
        log.setLevel(logging.DEBUG)

    masterGraph = PatchableGraph()
    reader = SimpleMFRC522()

    loop = ReadLoop(reader, masterGraph)

    port = 10012
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler,
         {"path": ".", "default_filename": "index.html"}),
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler,
         {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        ], masterGraph=masterGraph, debug=arg['-v']), interface='::')
    log.warn('serving on %s', port)

    reactor.run()
