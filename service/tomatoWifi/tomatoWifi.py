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
import web.utils
from cyclone.httpclient import fetch
sys.path.append("/home/drewp/projects/photo/lib/python2.7/site-packages")
from dateutil import tz
from twisted.internet import reactor, task
from twisted.internet.defer import inlineCallbacks

from pymongo import Connection, DESCENDING
from rdflib import Namespace, Literal, URIRef
sys.path.append("/my/site/magma")
from stategraph import StateGraph
from wifi import Wifi
from dhcpparse import addDhcpData

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
        def rowDict(row):
            row['cls'] = "signal" if row.get('connected') else "nosignal"
            if 'name' not in row:
                row['name'] = row.get('clientHostname', '-')
            if 'signal' not in row:
                row['signal'] = 'yes' if row['connected'] else 'no'

            try:
                conn = self.whenConnected(row['mac'])
                row['connectedAgo'] = web.utils.datestr(
                    conn.astimezone(tz.tzutc()).replace(tzinfo=None))
            except ValueError:
                pass
            
            return row

        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(pystache.render(
            open("table.mustache").read(),
            dict(
                rows=sorted(map(rowDict, self.settings.poller.lastAddrs),
                            key=lambda a: (not a.get('connected'),
                                           a.get('name'))))))

    def whenConnected(self, macThatIsNowConnected):
        lastArrive = None
        for ev in self.settings.mongo.find({'address': macThatIsNowConnected},
                                           sort=[('created', -1)],
                                           max_scan=100000):
            if ev['action'] == 'arrive':
                lastArrive = ev
            if ev['action'] == 'leave':
                break
        if lastArrive is None:
            raise ValueError("no past arrivals")
        
        return lastArrive['created']
        

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
            if not dev.get('connected'):
                continue
            uri = URIRef("http://bigasterisk.com/mac/%s" % dev['mac'].lower())
            g.add((uri, ROOM['macAddress'], Literal(dev['mac'].lower())))
            
            g.add((uri, ROOM['connected'], aps))
            if 'clientHostname' in dev:
                g.add((uri, ROOM['wifiNetworkName'], Literal(dev['clientHostname'])))
            if 'name' in dev:
                g.add((uri, ROOM['deviceName'], Literal(dev['name'])))
            if 'signal' in dev:
                g.add((uri, ROOM['signalStrength'], Literal(dev['signal'])))

        self.set_header('Content-type', 'application/x-trig')
        self.write(g.asTrig())

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
            addDhcpData(newAddrs)
            
            newWithSignal = [a for a in newAddrs if a.get('connected')]

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
                      timeout=2,
                      headers={'user-agent': ['tomatoWifi']}).addErrback(log.warn)
            self.lastAddrs = newAddrs
            self.lastPollTime = time.time()
        except Exception, e:
            log.error("poll error: %s\n%s", e, traceback.format_exc())

    def computeActions(self, newWithSignal):
        actions = []

        def makeAction(addr, act):
            d = dict(sensor="wifi",
                        address=addr.get('mac'),
                        name=addr.get('name'),
                        networkName=addr.get('clientHostname'),
                        action=act)
            if act == 'arrive' and 'ip' in addr:
                # this won't cover the possible case that you get on
                # wifi but don't have an ip yet. We'll record an
                # action with no ip and then never record your ip.
                d['ip'] = addr['ip']
            return d                             

        for addr in newWithSignal:
            if addr['mac'] not in [r['mac'] for r in self.lastWithSignal]:
                actions.append(makeAction(addr, 'arrive'))

        for addr in self.lastWithSignal:
            if addr['mac'] not in [r['mac'] for r in newWithSignal]:
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
    #log.setLevel(logging.DEBUG)

    mongo = Connection('bang', 27017, tz_aware=True)['visitor']['visitor']

    wifi = Wifi()
    poller = Poller(wifi, mongo)
    task.LoopingCall(poller.poll).start(1/config['pollFrequency'])

    reactor.listenTCP(config['servePort'],
                      cyclone.web.Application(
                          [
                              (r"/", Index),
                              (r'/json', Json),
                              (r'/graph', GraphHandler),
                              (r'/table', Table),
                              #(r'/activity', Activity),
                          ],
                          wifi=wifi,
                          poller=poller,
                          mongo=mongo))
    reactor.run()
