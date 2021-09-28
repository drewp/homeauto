"""
scrape the tomato router status pages to see who's connected to the
wifi access points. Includes leases that aren't currently connected.

Returns:
 json listing (for magma page)
 rdf graph (for reasoning)
 activity stream, when we start saving history

Todo: this should be the one polling and writing to mongo, not entrancemusic

"""
from collections import defaultdict
import datetime
import json
import logging
import sys
import time
import traceback
from typing import List

import ago
from cyclone.httpclient import fetch
import cyclone.web
from cycloneerr import PrettyErrorHandler
from dateutil import tz
import docopt
from patchablegraph import (
    CycloneGraphEventsHandler,
    CycloneGraphHandler,
    PatchableGraph,
)
from prometheus_client import Counter, Gauge, Summary
from prometheus_client.exposition import generate_latest
from prometheus_client.registry import REGISTRY
from pymongo import DESCENDING, MongoClient as Connection
from pymongo.collection import Collection
import pystache
from rdflib import ConjunctiveGraph, Literal, Namespace, RDF
from standardservice.logsetup import log
from twisted.internet import reactor, task
from twisted.internet.defer import ensureDeferred, inlineCallbacks

from scrape import SeenNode, Wifi

AST = Namespace("http://bigasterisk.com/")
DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")


class Index(PrettyErrorHandler, cyclone.web.RequestHandler):

    def get(self):
        age = time.time() - self.settings.poller.lastPollTime
        if age > 10:
            raise ValueError("poll data is stale. age=%s" % age)

        self.set_header("Content-Type", "text/html")
        self.write(open("index.html").read())


def whenConnected(mongo, macThatIsNowConnected):
    lastArrive = None
    for ev in mongo.find({'address': macThatIsNowConnected.upper()}, sort=[('created', -1)], max_time_ms=5000):
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
        self.write(
            pystache.render(
                open("table.mustache").read(),
                dict(rows=sorted(map(rowDict, self.settings.poller.lastAddrs),
                                 key=lambda a: (not a.get('connected'), a.get('name'))))))


class Json(PrettyErrorHandler, cyclone.web.RequestHandler):

    def get(self):
        self.set_header("Content-Type", "application/json")
        age = time.time() - self.settings.poller.lastPollTime
        if age > 10:
            raise ValueError("poll data is stale. age=%s" % age)
        self.write(json.dumps({"wifi": self.settings.poller.lastAddrs, "dataAge": age}))


POLL = Summary('poll', 'Time in HTTP poll requests')
POLL_SUCCESSES = Counter('poll_successes', 'poll success count')
POLL_ERRORS = Counter('poll_errors', 'poll error count')
CURRENTLY_ON_WIFI = Gauge('currently_on_wifi', 'current nodes known to wifi router (some may be wired)')
MAC_ON_WIFI = Gauge('connected', 'mac addr is currently connected', ['mac'])


class Poller(object):

    def __init__(self, wifi: Wifi, mongo: Collection):
        self.wifi = wifi
        self.mongo = mongo
        self.lastAddrs = []  # List[SeenNode]
        self.lastWithSignal = []
        self.lastPollTime = 0

    @POLL.time()
    async def poll(self):
        try:
            newAddrs = await self.wifi.getPresentMacAddrs()
            self.onNodes(newAddrs)
            POLL_SUCCESSES.inc()
        except Exception as e:
            log.error("poll error: %r\n%s", e, traceback.format_exc())
            POLL_ERRORS.inc()

    def onNodes(self, newAddrs: List[SeenNode]):
        now = int(time.time())
        newWithSignal = [a for a in newAddrs if a.connected]
        CURRENTLY_ON_WIFI.set(len(newWithSignal))

        actions = self.computeActions(newWithSignal)
        for action in actions:
            log.info("action: %s", action)
            action['created'] = datetime.datetime.now(tz.gettz('UTC'))
            mongo.save(action)
            MAC_ON_WIFI.labels(mac=action['address'].lower()).set(1 if action['action'] == 'arrive' else 0)
        if now // 3600 > self.lastPollTime // 3600:
            log.info('hourly writes')
            for addr in newWithSignal:
                MAC_ON_WIFI.labels(mac=addr.mac.lower()).set(1)

        self.lastWithSignal = newWithSignal
        self.lastAddrs = newAddrs
        self.lastPollTime = now

        self.updateGraph(masterGraph)

    def computeActions(self, newWithSignal):
        actions = []

        def makeAction(addr: SeenNode, act: str):
            d = dict(
                sensor="wifi",
                address=addr.mac.upper(),  # mongo data is legacy uppercase
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
        results = list(self.mongo.find({'name': name}).sort('created', DESCENDING).limit(1))
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

            for s, p, o in dev.stmts:
                g.add((s, p, o, ctx))

            try:
                conn = whenConnected(mongo, dev.mac)
            except ValueError:
                traceback.print_exc()
                pass
            else:
                g.add((dev.uri, ROOM['connectedAgo'], Literal(connectedAgoString(conn)), ctx))
                g.add((dev.uri, ROOM['connected'], Literal(conn), ctx))
        masterGraph.setToGraph(g)


class RemoteSuspend(PrettyErrorHandler, cyclone.web.RequestHandler):

    def post(self):
        # windows is running shutter (https://www.den4b.com/products/shutter)
        fetch('http://DESKTOP-GOU4AC4:8011/action', postdata={'id': 'Sleep'})


class Metrics(cyclone.web.RequestHandler):

    def get(self):
        self.add_header('content-type', 'text/plain')
        self.write(generate_latest(REGISTRY))


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

    mongo = Connection('mongodb.default.svc.cluster.local', 27017, tz_aware=True)['visitor']['visitor']

    config = ConjunctiveGraph()
    config.parse(open('private_config.n3'), format='n3')

    masterGraph = PatchableGraph()
    wifi = Wifi(config)
    poller = Poller(wifi, mongo)
    task.LoopingCall(lambda: ensureDeferred(poller.poll())).start(1 / float(args['--poll']))

    reactor.listenTCP(
        int(args['--port']),
        cyclone.web.Application(
            [
                (r"/", Index),
                (r"/build/(bundle\.js)", cyclone.web.StaticFileHandler, {
                    "path": 'build'
                }),
                (r'/json', Json),
                (r'/graph/wifi', CycloneGraphHandler, {
                    'masterGraph': masterGraph
                }),
                (r'/graph/wifi/events', CycloneGraphEventsHandler, {
                    'masterGraph': masterGraph
                }),
                (r'/table', Table),
                (r'/remoteSuspend', RemoteSuspend),
                (r'/metrics', Metrics),
                #(r'/activity', Activity),
            ],
            wifi=wifi,
            poller=poller,
            mongo=mongo))
    reactor.run()
