#!/usr/bin/python
"""
scrape the tomato router status pages to see who's connected to the
wifi access points. Includes leases that aren't currently connected.

Returns:
 json listing (for magma page)
 rdf graph (for reasoning)
 activity stream, when we start saving history

Todo: this should be the one polling and writing to mongo, not entrancemusic
"""
from __future__ import division
import sys, cyclone.web, json, traceback, time, pystache, datetime, logging
from cyclone.httpclient import fetch
sys.path.append("/home/drewp/projects/photo/lib/python2.7/site-packages")
from dateutil import tz
from twisted.internet import reactor, task
from twisted.internet.defer import inlineCallbacks, returnValue


from pymongo import Connection, DESCENDING
from rdflib import Namespace, Literal, URIRef
sys.path.append("/my/site/magma")
from stategraph import StateGraph
from wifi import Wifi

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

import rdflib
from rdflib import plugin
plugin.register(
  "sparql", rdflib.query.Processor,
  "rdfextras.sparql.processor", "Processor")
plugin.register(
  "sparql", rdflib.query.Result,
  "rdfextras.sparql.query", "SPARQLQueryResult")

DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")
reasoning = "http://bang:9071/"

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):

        age = time.time() - self.settings.poller.lastPollTime
        if age > 10:
            raise ValueError("poll data is stale. age=%s" % age)

        self.write("this is wifiusage. needs index page that embeds the table")

class Table(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        def rowDict(addr):
            addr['cls'] = "signal" if addr.get('signal') else "nosignal"
            if 'lease' in addr:
                addr['lease'] = addr['lease'].replace("0 days, ", "")
            return addr

        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(pystache.render(
            open("table.mustache").read(),
            dict(
                rows=sorted(map(rowDict, self.settings.poller.lastAddrs),
                            key=lambda a: (a.get('router'),
                                           a.get('name'),
                                           a.get('mac'))))))


class Json(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        age = time.time() - self.settings.poller.lastPollTime
        if age > 10:
            raise ValueError("poll data is stale. age=%s" % age)
        self.write(json.dumps({"wifi" : self.settings.poller.lastAddrs,
                                     "dataAge" : age}))

class GraphHandler(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        g = StateGraph(ctx=DEV['wifi'])

        # someday i may also record specific AP and their strength,
        # for positioning. But many users just want to know that the
        # device is connected to some bigasterisk AP.
        aps = URIRef("http://bigasterisk.com/wifiAccessPoints")
        age = time.time() - self.settings.poller.lastPollTime
        if age > 10:
            raise ValueError("poll data is stale. age=%s" % age)

        for dev in self.settings.poller.lastAddrs:
            if not dev.get('signal'):
                continue
            uri = URIRef("http://bigasterisk.com/wifiDevice/%s" % dev['mac'])
            g.add((uri, ROOM['macAddress'], Literal(dev['mac'])))
            g.add((uri, ROOM['connected'], aps))
            if 'rawName' in dev:
                g.add((uri, ROOM['wifiNetworkName'], Literal(dev['rawName'])))
            g.add((uri, ROOM['deviceName'], Literal(dev['name'])))
            g.add((uri, ROOM['signalStrength'], Literal(dev['signal'])))

        self.set_header('Content-type', 'application/x-trig')
        self.write(g.asTrig())

class Application(cyclone.web.Application):
    def __init__(self, wifi, poller):
        handlers = [
            (r"/", Index),
            (r'/json', Json),
            (r'/graph', GraphHandler),
            (r'/table', Table),
            #(r'/activity', Activity),
        ]
        settings = {
            'wifi' : wifi,
            'poller' : poller,
            'mongo' : Connection('bang', 27017,
                                 tz_aware=True)['house']['sensor']
            }
        cyclone.web.Application.__init__(self, handlers, **settings)

class Poller(object):
    def __init__(self, wifi, mongo):
        self.wifi = wifi
        self.mongo = mongo
        self.lastAddrs = []
        self.lastWithSignal = []
        self.lastPollTime = 0

    def assertCurrent(self):
        dt = time.time() - self.lastPollTime
        assert dt < 10, "last poll was %s sec ago" % dt

    @inlineCallbacks
    def poll(self):
        try:
            newAddrs = yield self.wifi.getPresentMacAddrs()

            newWithSignal = [a for a in newAddrs if a.get('signal')]

            actions = self.computeActions(newWithSignal)
            for action in actions:
                log.info("action: %s", action)
                action['created'] = datetime.datetime.now(tz.gettz('UTC'))
                mongo.save(action)
                try:
                    self.doEntranceMusic(action)
                except Exception, e:
                    log.error("entrancemusic error: %r", e)

            self.lastWithSignal = newWithSignal
            if actions: # this doesn't currently include signal strength changes
                fetch(reasoning + "immediateUpdate",
                      headers={'user-agent': 'tomatoWifi'}).addErrback(log.warn)
            self.lastAddrs = newAddrs
            self.lastPollTime = time.time()
        except Exception, e:
            log.error("poll error: %s\n%s", e, traceback.format_exc())

    def computeActions(self, newWithSignal):
        def removeVolatile(a):
            ret = dict((k,v) for k,v in a.items() if k in ['name', 'mac'])
            ret['signal'] = bool(a.get('signal'))
            return ret

        def find(a, others):
            a = removeVolatile(a)
            return any(a == removeVolatile(o) for o in others)

        actions = []

        def makeAction(addr, act):
            return dict(sensor="wifi",
                        address=addr.get('mac'),
                        name=addr.get('name'),
                        networkName=addr.get('rawName'),
                        action=act)

        for addr in newWithSignal:
            if not find(addr, self.lastWithSignal):
                # the point of all the removeVolatile stuff is so
                # I have the complete addr object here, although
                # it is currently mostly thrown out by makeAction
                actions.append(makeAction(addr, 'arrive'))

        for addr in self.lastWithSignal:
            if not find(addr, newWithSignal):
                actions.append(makeAction(addr, 'leave'))

        return actions


    # these need to move out to their own service
    def doEntranceMusic(self, action):
        import restkit, jsonlib
        dt = self.deltaSinceLastArrive(action['name'])
        log.debug("dt=%s", dt)
        if dt > datetime.timedelta(hours=1):
            hub = restkit.Resource(
                # PSHB not working yet; "http://bang:9030/"
                "http://slash:9049/"
                )
            action = action.copy()
            del action['created']
            del action['_id']
            log.info("post to %s", hub)
            hub.post("visitorNet", payload=jsonlib.dumps(action))

    def deltaSinceLastArrive(self, name):
        results = list(self.mongo.find({'name' : name}).sort('created',
                                                         DESCENDING).limit(1))
        if not results:
            return datetime.timedelta.max
        now = datetime.datetime.now(tz.gettz('UTC'))
        last = results[0]['created'].replace(tzinfo=tz.gettz('UTC'))
        return now - last


if __name__ == '__main__':
    config = {
        'servePort' : 9070,
        'pollFrequency' : 1/5,
        }
    from twisted.python import log as twlog
    #log.startLogging(sys.stdout)
    #log.setLevel(10)
    log.setLevel(logging.DEBUG)

    mongo = Connection('bang', 27017)['visitor']['visitor']

    wifi = Wifi()
    poller = Poller(wifi, mongo)
    task.LoopingCall(poller.poll).start(1/config['pollFrequency'])

    reactor.listenTCP(config['servePort'], Application(wifi, poller))
    reactor.run()
