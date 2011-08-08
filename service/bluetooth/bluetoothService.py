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
import logging, time, datetime, restkit, jsonlib, cyclone.web, sys
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

mongo = Connection('bang', 27017)['visitor']['visitor']

ROOM = Namespace("http://projects.bigasterisk.com/room/")

def getNearbyDevices():
    addrs = discover_devices()

    # this can be done during discover_devices, but my plan was to
    # cache it more in here
    names = dict((a, lookup_name(a)) for a in addrs)
    log.debug("discover found %r %r", addrs, names)
    return addrs, names

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
        if msg['name'] != 'THINKPAD_T43':
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

    def compare(self, (addrs, names)):
        self.lastPollTime = time.time()

        newGraph = Graph()
        addrs = set(addrs)
        for addr in addrs.difference(self.lastAddrs):
            self.recordAction('arrive', addr, names)
        for addr in self.lastAddrs.difference(addrs):
            self.recordAction('leave', addr, names)
        for addr in addrs:
            uri = deviceUri(addr)
            newGraph.add((ROOM['bluetooth'], ROOM['senses'], uri))
            if addr in names:
                newGraph.add((uri, RDFS.label, Literal(names[addr])))
        self.lastAddrs = addrs
        self.currentGraph = newGraph

    def recordAction(self, action, addr, names):
        doc = {"sensor" : "bluetooth",
               "address" : addr,
               "action" : action}
        if addr in names:
            doc["name"] = names[addr]
        log.info("action: %s", doc)
        mongoInsert(doc)

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        age = time.time() - self.settings.poller.lastPollTime
        if age > self.settings.config['period'] + 30:
            raise ValueError("poll data is stale. age=%s" % age)
        
        self.write("bluetooth watcher. ")

if __name__ == '__main__':
    config = {
        "period" : 60,
        }
    log.setLevel(logging.INFO)
    poller = Poller()
    reactor.listenTCP(9077, cyclone.web.Application([
        (r'/', Index),
        # graph, json, table, ...
        ], poller=poller, config=config))
    task.LoopingCall(poller.poll).start(config['period'])
    reactor.run()
