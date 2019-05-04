"""
scrape the tomato router status pages to see who's connected to the
wifi access points. Includes leases that aren't currently connected.

Returns:
 json listing (for magma page)
 rdf graph (for reasoning)
 activity stream, when we start saving history

Todo: this should be the one polling and writing to mongo, not entrancemusic

"""
import sys, json, traceback, time, datetime, logging
from typing import List

from cyclone.httpclient import fetch
from dateutil import tz
from influxdb import InfluxDBClient
from pymongo import MongoClient as Connection, DESCENDING
from rdflib import Namespace, Literal, ConjunctiveGraph, RDF
from twisted.internet import reactor, task
from twisted.internet.defer import inlineCallbacks
import ago
import cyclone.web
import docopt
import pystache

from cycloneerr import PrettyErrorHandler
from standardservice.logsetup import log
from patchablegraph import PatchableGraph, CycloneGraphEventsHandler, CycloneGraphHandler
from scrape import Wifi, SeenNode

AST = Namespace("http://bigasterisk.com/")
DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")
reasoning = "http://bang:9071/"

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        age = time.time() - self.settings.poller.lastPollTime
        if age > 10:
            raise ValueError("poll data is stale. age=%s" % age)
            
        self.set_header("Content-Type", "text/html")
        self.write(open("index.html").read())

def whenConnected(mongo, macThatIsNowConnected):
    lastArrive = None
    for ev in mongo.find({'address': macThatIsNowConnected.upper()},
                         sort=[('created', -1)],
                         max_scan=100000):
        if ev['action'] == 'arrive':
            lastArrive = ev
        if ev['action'] == 'leave':
            break
    if lastArrive is None:
        raise ValueError("no past arrivals")

    return lastArrive['created']

def connectedAgoString(conn):
    return ago.human(conn.astimezone(tz.tzutc()).replace(tzinfo=None))
    
class Table(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        def rowDict(row):
            row['cls'] = "signal" if row.get('connected') else "nosignal"
            if 'name' not in row:
                row['name'] = row.get('clientHostname', '-')
            if 'signal' not in row:
                row['signal'] = 'yes' if row.get('connected') else 'no'

            try:
                conn = whenConnected(self.settings.mongo, row.get('mac', '??'))
                row['connectedAgo'] = connectedAgoString(conn)
            except ValueError:
                row['connectedAgo'] = 'yes' if row.get('connected') else ''
            row['router'] = row.get('ssid', '')
            return row

        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(pystache.render(
            open("table.mustache").read(),
            dict(
                rows=sorted(map(rowDict, self.settings.poller.lastAddrs),
                            key=lambda a: (not a.get('connected'),
                                           a.get('name'))))))

class Json(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        age = time.time() - self.settings.poller.lastPollTime
        if age > 10:
            raise ValueError("poll data is stale. age=%s" % age)
        self.write(json.dumps({"wifi" : self.settings.poller.lastAddrs,
                               "dataAge" : age}))

class Poller(object):
    def __init__(self, wifi, mongo):
        self.wifi = wifi
        self.mongo = mongo
        self.lastAddrs = [] # List[SeenNode]
        self.lastWithSignal = []
        self.lastPollTime = 0

    def assertCurrent(self):
        dt = time.time() - self.lastPollTime
        assert dt < 10, "last poll was %s sec ago" % dt

    @inlineCallbacks
    def poll(self):     
        try:
            newAddrs = yield self.wifi.getPresentMacAddrs()
            self.onNodes(newAddrs)
        except Exception as e:
            log.error("poll error: %r\n%s", e, traceback.format_exc())

    def onNodes(self, newAddrs: List[SeenNode]):
        now = int(time.time())
        newWithSignal = [a for a in newAddrs if a.connected]

        actions = self.computeActions(newWithSignal)
        points = []
        for action in actions:
            log.info("action: %s", action)
            action['created'] = datetime.datetime.now(tz.gettz('UTC'))
            mongo.save(action)
            points.append(
                self.influxPoint(now, action['address'].lower(),
                                 1 if action['action'] == 'arrive' else 0))
        if now // 3600 > self.lastPollTime // 3600:
            log.info('hourly writes')
            for addr in newWithSignal:
                points.append(self.influxPoint(now, addr.mac.lower(), 1))

        influx.write_points(points, time_precision='s')
        self.lastWithSignal = newWithSignal
        if actions: # this doesn't currently include signal strength changes
            fetch(reasoning + "immediateUpdate",
                  method='PUT',
                  timeout=2,
                  headers={'user-agent': ['wifi']}).addErrback(log.warn)
        self.lastAddrs = newAddrs
        self.lastPollTime = now

        self.updateGraph(masterGraph)
            
    def influxPoint(self, now, address, value):
        return {
            'measurement': 'presence',
            'tags': {'sensor': 'wifi', 'address': address,},
            'fields': {'value': value},
            'time': now,
        }
        
    def computeActions(self, newWithSignal):
        actions = []

        def makeAction(addr: SeenNode, act: str):
            d = dict(sensor="wifi",
                     address=addr.mac.upper(), # mongo data is legacy uppercase
                     action=act)
            if act == 'arrive':
                # this won't cover the possible case that you get on
                # wifi but don't have an ip yet. We'll record an
                # action with no ip and then never record your ip.
                d['ip'] = addr.ip
            return d                             

        for addr in newWithSignal:
            if addr.mac not in [r.mac for r in self.lastWithSignal]:
                actions.append(makeAction(addr, 'arrive'))

        for addr in self.lastWithSignal:
            if addr.mac not in [r.mac for r in newWithSignal]:
                actions.append(makeAction(addr, 'leave'))

        return actions

    def deltaSinceLastArrive(self, name):
        results = list(self.mongo.find({'name' : name}).sort('created',
                                                         DESCENDING).limit(1))
        if not results:
            return datetime.timedelta.max
        now = datetime.datetime.now(tz.gettz('UTC'))
        last = results[0]['created'].replace(tzinfo=tz.gettz('UTC'))
        return now - last

    def updateGraph(self, masterGraph):
        g = ConjunctiveGraph()
        ctx = DEV['wifi']

        # someday i may also record specific AP and their strength,
        # for positioning. But many users just want to know that the
        # device is connected to some bigasterisk AP.
        age = time.time() - self.lastPollTime
        if age > 10:
            raise ValueError("poll data is stale. age=%s" % age)

        for dev in self.lastAddrs:
            if not dev.connected:
                continue
            g.add((dev.uri, RDF.type, ROOM['NetworkedDevice'], ctx))
            g.add((dev.uri, ROOM['macAddress'], Literal(dev.mac), ctx))
            g.add((dev.uri, ROOM['ipAddress'], Literal(dev.ip), ctx))

            for s,p,o in dev.stmts:
                g.add((s, p, o, ctx))

            try:
                conn = whenConnected(mongo, dev.mac)
            except ValueError:
                traceback.print_exc()
                pass
            else:
                g.add((dev.uri, ROOM['connectedAgo'],
                       Literal(connectedAgoString(conn)), ctx))
                g.add((dev.uri, ROOM['connected'], Literal(conn), ctx))
        masterGraph.setToGraph(g)


if __name__ == '__main__':
    args = docopt.docopt('''
Usage:
  wifi.py [options]

Options:
  -v, --verbose  more logging
  --port=<n>     serve on port [default: 9070]
  --poll=<freq>  poll frequency [default: .2]
''')
    if args['--verbose']:
        from twisted.python import log as twlog
        twlog.startLogging(sys.stdout)
        log.setLevel(10)
        log.setLevel(logging.DEBUG)

    mongo = Connection('bang', 27017, tz_aware=True)['visitor']['visitor']
    influx = InfluxDBClient('bang', 9060, 'root', 'root', 'main')

    config = ConjunctiveGraph()
    config.parse(open('private_config.n3'), format='n3')
    
    masterGraph = PatchableGraph()
    wifi = Wifi(config)
    poller = Poller(wifi, mongo)
    task.LoopingCall(poller.poll).start(1/float(args['--poll']))

    reactor.listenTCP(
        int(args['--port']),
        cyclone.web.Application(
            [
                (r"/", Index),
                (r'/json', Json),
                (r'/graph', CycloneGraphHandler, {'masterGraph': masterGraph}),
                (r'/graph/events', CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
                (r'/table', Table),
                #(r'/activity', Activity),
            ],
            wifi=wifi,
            poller=poller,
            mongo=mongo))
    reactor.run()
