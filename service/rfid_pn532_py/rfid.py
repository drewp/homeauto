import os
os.environ['LIBNFC_DEFAULT_DEVICE'] = "pn532_uart:/dev/ttyUSB0"

from docopt import docopt
from rdfdb.patch import Patch
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task, defer
import cyclone.web
from cyclone.httpclient import fetch
import cyclone
import logging, time, json, random, string, traceback
from logsetup import log, enableTwistedLog
from greplin import scales
from greplin.scales.cyclonehandler import StatsHandler
from export_to_influxdb import InfluxExporter
from tags import NfcDevice, FakeNfc, NfcError, AuthFailedError

ROOM = Namespace('http://projects.bigasterisk.com/room/')

ctx = ROOM['frontDoorWindowRfidCtx']

STATS = scales.collection('/root',
                          scales.PmfStat('cardReadPoll'),
                          scales.IntStat('newCardReads'),
)

class OutputPage(cyclone.web.RequestHandler):
    def put(self):
        arg = self.request.arguments
        if arg.get('s') and arg.get('p'):
            self._onQueryStringStatement(arg['s'][-1], arg['p'][-1], self.request.body)
        else:
            self._onGraphBodyStatements(self.request.body, self.request.headers)
    post = put
    def _onQueryStringStatement(self, s, p, body):
        subj = URIRef(s)
        pred = URIRef(p)
        turtleLiteral = self.request.body
        try:
            obj = Literal(float(turtleLiteral))
        except ValueError:
            obj = Literal(turtleLiteral)
        self._onStatements([(subj, pred, obj)])
        
    def _onGraphBodyStatements(self, body, headers):
        g = Graph()
        g.parse(StringInputSource(body), format='nt')
        if not g:
            raise ValueError("expected graph body")
        self._onStatements(list(g.triples((None, None, None))))
    post = put
    
    def _onStatements(self, stmts):
        # write rfid to new key, etc.
        if len(stmts) > 0 and stmts[0][1] == ROOM['keyContents']:
            return
        log.warn("ignoring %s", stmts)

def uidUri(card_id):
    return URIRef('http://bigasterisk.com/rfidCard/%s' % card_id)

BODY_VERSION = "1"
def randomBody():
    return BODY_VERSION + '*' + ''.join(random.choice(string.ascii_uppercase) for n in range(16 - 2))

def looksLikeBigasterisk(text):
    return text.startswith(BODY_VERSION + "*")
    
class Rewrite(cyclone.web.RequestHandler):
    def post(self):
        agent = URIRef(self.request.headers['x-foaf-agent'])
        body = json.loads(self.request.body)

        _, uid = reader.read_id()
        log.info('current card id: %r %r', _, uid)
        if uid is None:
            self.set_status(404, "no card present")
            # maybe retry a few more times since the card might be nearby
            return
            
        text = randomBody()
        log.info('%s rewrites %s to %s, to be owned by %s', 
                 agent, uid, text, body['user'])
        
        #reader.KEY = private.rfid_key
        reader.write(uid, text)
        log.info('done with write')

    
sensor = ROOM['frontDoorWindowRfid']

class ReadLoop(object):
    def __init__(self, reader, masterGraph, overwrite_any_tag):
        self.reader = reader
        self.masterGraph = masterGraph
        self.overwrite_any_tag = overwrite_any_tag
        self.log = {} # cardIdUri : most recent seentime

        self.pollPeriodSecs = .1
        self.expireSecs = 5
        
        task.LoopingCall(self.poll).start(self.pollPeriodSecs)

    @STATS.cardReadPoll.time()
    def poll(self):
        now = time.time()

        self.flushOldReads(now)

        try:
            for tag in self.reader.getTags(): # blocks for a bit
                uid = tag.uid()
                log.debug('detected tag uid=%r', uid)
                cardIdUri = uidUri(uid)

                is_new = cardIdUri not in self.log
                self.log[cardIdUri] = now
                if is_new:
                    STATS.newCardReads += 1
                    tag.connect()
                    try:
                        textLit = Literal(tag.readBlock(1).rstrip('\x00'))
                        if self.overwrite_any_tag and not looksLikeBigasterisk(textLit):
                            log.info("block 1 was %r; rewriting it", textLit)
                            tag.writeBlock(1, randomBody())
                            textLit = Literal(tag.readBlock(1).rstrip('\x00'))
                    finally:
                        # This might not be appropriate to call after
                        # readBlock fails. I am getting double
                        # exceptions.
                        tag.disconnect()
                    self.startCardRead(cardIdUri, textLit)
        except AuthFailedError as e:
            log.error(e)
        except (NfcError, OSError) as e:
            traceback.print_exc()
            log.error(e)
            reactor.stop()
    def flushOldReads(self, now):
        for uri in list(self.log):
            if self.log[uri] < now - self.expireSecs:
                self.endCardRead(uri)
                del self.log[uri]

    def startCardRead(self, cardUri, text):
        self.masterGraph.patch(Patch(addQuads=[
            (sensor, ROOM['reading'], cardUri, ctx),
            (cardUri, ROOM['cardText'], text, ctx)],
                                     delQuads=[]))
        log.info('%s :cardText %s .', cardUri.n3(), text.n3())
        self._sendOneshot([(sensor, ROOM['startReading'], cardUri),
                            (cardUri, ROOM['cardText'], text)])

    def endCardRead(self, cardUri):
        log.debug(f'{cardUri} has been gone for {self.expireSecs} sec')
        delQuads = []
        for spo in self.masterGraph._graph.triples(
                (sensor, ROOM['reading'], cardUri)):
            delQuads.append(spo + (ctx,))
        for spo in self.masterGraph._graph.triples(
                (cardUri, ROOM['cardText'], None)):
            delQuads.append(spo + (ctx,))
            
        self.masterGraph.patch(Patch(addQuads=[], delQuads=delQuads))
        
    def _sendOneshot(self, oneshot):
        body = (' '.join('%s %s %s .' % (s.n3(), p.n3(), o.n3())
                         for s,p,o in oneshot)).encode('utf8')
        url = b'http://bang:9071/oneShot'
        d = fetch(method=b'POST',
                  url=url,
                  headers={b'Content-Type': [b'text/n3']},
                  postdata=body,
                  timeout=5)
        def err(e):
            log.info('oneshot post to %r failed:  %s',
                     url, e.getErrorMessage())
        d.addErrback(err)

                                                              
        
if __name__ == '__main__':
    arg = docopt("""
    Usage: rfid.py [options]

    -v                    Verbose
    --overwrite_any_tag   Rewrite any unknown tag with a new random body
    -n                    Fake reader
    """)
    log.setLevel(logging.INFO)
    if arg['-v']:
        enableTwistedLog()
        log.setLevel(logging.DEBUG)
        log.info(f'cyclone {cyclone.__version__}')
        
    masterGraph = PatchableGraph()
    reader = NfcDevice() if not arg['-n'] else FakeNfc()

    ie=InfluxExporter(Graph())
    ie.exportStats(STATS, ['root.cardReadPoll.count',
                           'root.cardReadPoll.95percentile',
                           'root.newCardReads',
                       ],
                    period_secs=10,
                    retain_days=7,
    )

    loop = ReadLoop(reader, masterGraph, overwrite_any_tag=arg['--overwrite_any_tag'])

    port = 10012
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/(|.+\.html)", cyclone.web.StaticFileHandler,
         {"path": ".", "default_filename": "index.html"}),
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler,
         {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        (r'/rewrite', Rewrite),
        (r'/stats/(.*)', StatsHandler, {'serverName': 'rfid'}),
        ], masterGraph=masterGraph, debug=arg['-v']), interface='::')
    log.warn('serving on %s', port)

    reactor.run()
