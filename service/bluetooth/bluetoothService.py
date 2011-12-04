#!/usr/bin/python

"""
watch for bluetooth devices

this discoverer finds me if my treo has its screen on only, so I
have to wake up my own treo for a few seconds. 

I can use 'hcitool cc <addr> && hcitool rssi <addr>' to wake it up and
get its signal strength, but that pattern crashes my treo easily. I
still don't have an access that wakes up the treo and then doesn't
crash it. Maybe I could pretend to be a headset or something.

depends on ubuntu package: python-bluez

"""
from __future__ import absolute_import
import logging, time, datetime, restkit, jsonlib, sys, socket
import cyclone.web, pystache
from dateutil.tz import tzutc, tzlocal
from bluetooth import discover_devices, lookup_name
from twisted.internet import reactor, task
from twisted.internet.threads import deferToThread
from rdflib.Graph import Graph
from rdflib import Literal, Namespace, RDFS, URIRef
from pymongo import Connection
from dateutil import tz

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

mongo = Connection('bang', 27017, tz_aware=True)['visitor']['visitor']

ROOM = Namespace("http://projects.bigasterisk.com/room/")

# the mongodb serves as a much bigger cache, but I am expecting that
# 1) i won't fill memory with too many names; 2) this process will see
# each new device before it leaves, so I'll have the leaving name in
# my cache
nameCache = {} # addr : name

def lookupPastName(addr):
    row = mongo.find_one({"address" : addr,
                          'name' : {'$exists' : True}},
                         sort=[("created",-1)])
    if row is None:
        return None
    return row['name']

def getNearbyDevices():
    addrs = discover_devices()

    for a in addrs:
        if a not in nameCache:
            n = lookup_name(a) or lookupPastName(a)
            if n is not None:
                nameCache[a] = n
                
    log.debug("discover found %r", addrs)
    return addrs

hub = restkit.Resource(
    # PSHB not working yet; "http://bang:9030/"
    "http://slash:9049/"
    )

def mongoInsert(msg):
    try:
        js = jsonlib.dumps(msg)
    except UnicodeDecodeError:
        pass
    else:
        if (msg.get('name', '') and
            msg['name'] not in ['THINKPAD_T43'] and
            msg['action'] == 'arrive'):
            hub.post("visitorNet", payload=js) # sans datetime
    msg['created'] = datetime.datetime.now(tz.gettz('UTC'))
    mongo.insert(msg, safe=True)

def deviceUri(addr):
    return URIRef("http://bigasterisk.com/bluetooth/%s" % addr)

class Poller(object):
    def __init__(self):
        self.lastAddrs = set() # addresses
        self.currentGraph = Graph()
        self.lastPollTime = 0

    def poll(self):
        log.debug("get devices")
        devs = deferToThread(getNearbyDevices)

        devs.addCallback(self.compare)
        devs.addErrback(log.error)
        return devs

    def compare(self, addrs):
        self.lastPollTime = time.time()

        newGraph = Graph()
        addrs = set(addrs)
        for addr in addrs.difference(self.lastAddrs):
            self.recordAction('arrive', addr)
        for addr in self.lastAddrs.difference(addrs):
            self.recordAction('leave', addr)
        for addr in addrs:
            uri = deviceUri(addr)
            newGraph.add((ROOM['bluetooth'], ROOM['senses'], uri))
            if addr in nameCache:
                newGraph.add((uri, RDFS.label, Literal(nameCache[addr])))
        self.lastAddrs = addrs
        self.currentGraph = newGraph

    def recordAction(self, action, addr):
        doc = {"sensor" : "bluetooth",
               "address" : addr,
               "action" : action}
        if addr in nameCache:
            doc["name"] = nameCache[addr]
        log.info("action: %s", doc)
        mongoInsert(doc)

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        age = time.time() - self.settings.poller.lastPollTime
        if age > self.settings.config['period'] + 30:
            raise ValueError("poll data is stale. age=%s" % age)

        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(pystache.render(
            open("index.xhtml").read(),
            dict(host=socket.gethostname(),
                 )))

class Recent(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        name = {}  # addr : name
        events = []
        hours = float(self.get_argument("hours", default="3"))
        t1 = datetime.datetime.now(tzutc()) - datetime.timedelta(seconds=60*60*hours)
        for row in mongo.find({"sensor":"bluetooth",
                               "created":{"$gt":t1}}, sort=[("created", 1)]):
            if 'name' in row:
                name[row['address']] = row['name']
            row['t'] = int(row['created'].astimezone(tzlocal()).strftime("%s"))
            del row['created']
            del row['_id']
            events.append(row)

        for r in events:
            r['name'] = name.get(r['address'], r['address'])
        self.set_header("Content-Type", "application/json")
        self.write(jsonlib.dumps({"events" : events}))
           

class Static(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self, fn):
        self.write(open(fn).read())

if __name__ == '__main__':
    config = {
        "period" : 60,
        }
    log.setLevel(logging.INFO)
    poller = Poller()
    reactor.listenTCP(9077, cyclone.web.Application([
        (r'/', Index),
        (r'/recent', Recent),
        (r'/(underscore-min.js|pretty.js)', Static),
        # graph, json, table, ...
        ], poller=poller, config=config))
    task.LoopingCall(poller.poll).start(config['period'])
    reactor.run()
