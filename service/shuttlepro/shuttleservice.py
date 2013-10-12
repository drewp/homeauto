import sys, time
import cyclone.web, cyclone.httpclient, cyclone.websocket
sys.path.append("../../lib")
from logsetup import log
from cycloneerr import PrettyErrorHandler
from twisted.internet import reactor, threads
from shuttlepro import powermate
sys.path.append("/my/site/magma")
from stategraph import StateGraph

from rdflib import Namespace, Graph, Literal
SHUTTLEPRO = Namespace("http://bigasterisk.com/room/livingRoom/shuttlepro/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

def sendOneShotGraph(g):
    if not g:
        return

    nt = g.serialize(format='nt')
    cyclone.httpclient.fetch(
        "http://bang:9071/oneShot",
        method='POST',
        postdata=nt,
        timeout=1,
        headers={'Content-Type': ['text/n3']},
    ).addErrback(log.error)

class Index(PrettyErrorHandler, cyclone.web.StaticFileHandler):
    def get(self, *args, **kw):
        self.settings.poller.assertCurrent()
        return cyclone.web.StaticFileHandler.get(self, *args, **kw)

class GraphResource(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        p = self.settings.poller
        g = StateGraph(ROOM.environment)
        g.add((SHUTTLEPRO['shuttle'], ROOM['angle'],
               Literal(p.currentShuttleAngle)))
        g.add((SHUTTLEPRO['dial'], ROOM['totalDialMovement'],
               Literal(p.totalDialMovement)))
        self.set_header('Content-type', 'application/x-trig')
        self.write(g.asTrig())

class Poller(object):
    def __init__(self, dev="/dev/input/by-id/usb-Contour_Design_ShuttlePRO-event-if00"):
        self.lastUpdateTime = 0
        self.p = powermate(dev, self.onEvent)
        self.updateLoop()
        self.currentShuttleAngle = 0
        self.totalDialMovement = 0

    def assertCurrent(self):
        ago = time.time() - self.lastUpdateTime
        if ago > 60: # this may have to go up depending on how read_next times out
            raise ValueError("last usb update was %s sec ago" % ago)
        
    def onEvent(self, what):
        print 'onEvent', what
        g = Graph()
        if 'key' in what:
            g.add((SHUTTLEPRO['button%s' % what['key']['button']],
                   ROOM['state'],
                   ROOM['press'] if what['key']['press'] else ROOM['release']))
        elif 'shuttle' in what:
            # this will send lots of repeats. It's really not a one-shot at all.
            g.add((SHUTTLEPRO['shuttle'], ROOM['position'],
                   Literal(what['shuttle'])))
            self.currentShuttleAngle = what['shuttle']
        elif 'dial' in what:
            g.add((SHUTTLEPRO['dial'], ROOM['change'],
                   ROOM['clockwise'] if what['dial'] == 1 else
                   ROOM['counterclockwise']))
            self.totalDialMovement += what['dial']
        sendOneShotGraph(g)

    def updateLoop(self, *prevResults):
        self.lastUpdateTime = time.time()
        threads.deferToThread(
            self.p.read_next
        ).addCallback(self.updateLoop)
        
if __name__ == '__main__':
    from twisted.python import log as twlog
    twlog.startLogging(sys.stdout)
    port = 9103
    poller = Poller()
    reactor.listenTCP(port, cyclone.web.Application(handlers=[
        (r'/()', Index, {"path" : ".", "default_filename" : "index.html"}),
        (r'/graph', GraphResource),
        # serves this source code too
        (r'/(.*)', cyclone.web.StaticFileHandler, {"path" : "."}) 
        ], poller=poller))
    log.info("serving on %s" % port)
    reactor.run()
