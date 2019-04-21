# not in use- see rfid.nim

import os
from docopt import docopt
from rdfdb.patch import Patch
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.parser import StringInputSource
from twisted.internet import reactor, task, defer
import cyclone.web
from cyclone.httpclient import fetch
import logging, time, json, random, string
from logsetup import log, enableTwistedLog
import private
from greplin import scales
from greplin.scales.cyclonehandler import StatsHandler
from pynfc.ntag_read import NTagReadWrite

ROOM = Namespace('http://projects.bigasterisk.com/room/')

ctx = ROOM['frontDoorWindowRfidCtx']

cardOwner = {
    URIRef('http://bigasterisk.com/rfidCard/93a7591a77'):
    URIRef('http://bigasterisk.com/foaf.rdf#drewp'),
}

STATS = scales.collection('/web',
                          scales.PmfStat('cardReadPoll'),
)
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

def uidUri(card_id):
    return URIRef('http://bigasterisk.com/rfidCard/%s' %
                  binascii.hexlify(card_id))
        
def uidArray(uri):
    prefix, h = uri.rsplit('/', 1)
    if prefix != 'http://bigasterisk.com/rfidCard':
        raise ValueError(uri)
    return [int(h[i * 2: i * 2 + 2], 16) for i in range(0, len(h), 2)]
        
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
            
        text = ''.join(random.choice(string.uppercase) for n in range(32))
        log.info('%s rewrites %s to %s, to be owned by %s', 
                 agent, uid, text, body['user'])
        
        #reader.KEY = private.rfid_key
        reader.write(uid, text)
        log.info('done with write')

    
sensor = ROOM['frontDoorWindowRfid']
from pynfc.ntag_read import TagType
import binascii
class ReadLoop(object):
    def __init__(self, reader, masterGraph):
        self.reader = reader
        self.masterGraph = masterGraph
        self.log = {} # cardIdUri : most recent seentime

        self.pollPeriodSecs = .1
        self.expireSecs = 2
        
        task.LoopingCall(self.poll).start(self.pollPeriodSecs)

    @STATS.cardReadPoll.time()
    def poll(self):
        now = time.time()

        self.flushOldReads(now)

        log.info('scanning for cards')
        uids = self.reader.list_targets()
        log.info(f'reader sees {uids}')
        if len(uids) > 1:
            print("Found {count} uids: {uids}. Please remove all but one from the device".format(count=len(uids), uids=uids))
            return

        tt = TagType.NTAG_216

        print('detrm tag type', self.reader.determine_tag_type())

        
        uid = self.reader.setup_target()
        print("uid = {}".format(binascii.hexlify(uid)))

        self.reader.set_easy_framing()
        um_fast = self.reader.read_user_memory(tt)

        print(f'read {um_fast} on {uids[0]}')
        text = um_fast

        cardIdUri = uidUri(uid)
        textLit = Literal(text.rstrip().decode('ascii', 'replace'))

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
                            (cardUri, ROOM['cardText'], text, ctx)],
                  delQuads=[])
        self.masterGraph.patch(p)
        log.info('read card: id=%s %r', cardUri, str(text))
        self._sendOneshot([(sensor, ROOM['startReading'], cardUri),
                            (cardUri, ROOM['cardText'], text)])

    def endCardRead(self, cardUri):
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
        defer.setDebugging(True)
        print('defer log')

    masterGraph = PatchableGraph()
    os.environ['LIBNFC_DEFAULT_DEVICE'] = "pn532_i2c:/dev/i2c-1"


    import ctypes
    import pynfc.mifareauth
    r = pynfc.mifareauth.NFCReader(log.info)
    while True:
        try:
            r.run()
        except IOError:
            pass
            
#    import pynfc as nfc
#    context = ctypes.pointer(nfc.nfc_context())
#    nfc.nfc_init(ctypes.byref(context))
#
#    conn_strings = (nfc.nfc_connstring * 10)()
#    devices_found = nfc.nfc_list_devices(context, conn_strings, 10)
#    device = nfc.nfc_open(context, conn_strings[0])
#    r.__device = device
#    
#    print('initd')
#    try:
#        print('selecting')
#        uid = r.select_card()
#        print('sel', uid)
#        r.read_card(uid)
#        
#    finally:
#        nfc.nfc_close(dev)
    
    #conn_strings = (nfc.nfc_connstring * 10)()
    #devices_found = nfc.nfc_list_devices(
    #    context, conn_strings, 10)
    #if devices_found >= 1:
    #    dev = nfc.nfc_open(context, conn_strings[0])
    #try:
    #    _ = nfc.nfc_initiator_init(dev)
    #    print(f'found {dev.}')

    1/0
    reader = NTagReadWrite(log)

    loop = ReadLoop(reader, masterGraph)

    port = 10012
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler,
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
