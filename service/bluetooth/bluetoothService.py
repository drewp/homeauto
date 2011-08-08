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
from bluetooth import DeviceDiscoverer
from twisted.internet import reactor, defer, task
from rdflib.Graph import Graph
from rdflib import Literal, Variable, Namespace
from pymongo import Connection
from dateutil import tz

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

mongo = Connection('bang', 27017)['visitor']['visitor']

ROOM = Namespace("http://projects.bigasterisk.com/room/")

class Disco(DeviceDiscoverer):
    # it might be cool if this somehow returned
    # _bt.EVT_INQUIRY_RESULT_WITH_RSSI: results. see
    # /usr/share/pycentral/python-bluez/site-packages/bluetooth.py
    def device_discovered(self, address, device_class, name):
        log.debug("seeing: %s - %s (class 0x%X)" % (address, name, device_class))
        self.nearby.append((address, name))

    def inquiry_complete(self):
        pass
    
    def process_inquiry(self):
        # more async version of the normal method
        """
        Starts calling process_event, returning a deferred that fires
        when we're done.
        """
        self.done_inquiry = defer.Deferred()
        
        if self.is_inquiring or len(self.names_to_find) > 0:
            self.keep_processing()
        else:
            self.done_inquiry.callback(None)

        return self.done_inquiry

    def keep_processing(self):
        # this one still blocks "a little bit"
        if self.is_inquiring or len(self.names_to_find) > 0:
            reactor.callLater(0, self.keep_processing)
            log.debug("process_event()")
            self.process_event() # <-- blocks here
        else:
            self.done_inquiry.callback(None)

    def nearbyDevices(self):
        """deferred to list of (addr,name) pairs"""
        self.nearby = []
        self.find_devices()
        d = self.process_inquiry()
        d.addCallback(lambda result: self.nearby)
        return d

def devicesFromAddress(address):
    for row in graph.query(
        "SELECT ?dev { ?dev rm:bluetoothAddress ?addr }",
        initNs=dict(rm=ROOM),
        initBindings={Variable("?addr") : Literal(address)}):
        (dev,) = row
        yield dev
                        
graph = Graph()
graph.parse("phones.n3", format="n3")

d = Disco()
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

class Poller(object):
    def __init__(self):
        self.lastDevs = set() # addresses
        self.lastNameForAddress = {}
        self.currentGraph = Graph()
        self.lastPollTime = 0

    def poll(self):
        log.debug("get devices")
        devs = d.nearbyDevices()

        devs.addCallback(self.compare)
        devs.addErrback(log.error)
        return devs

    def compare(self, newDevs):
        self.lastPollTime = time.time()
        log.debug("got: %r", newDevs)
        lostDevs = self.lastDevs.copy()
        prevDevs = self.lastDevs.copy()
        self.lastDevs.clear()
        stmts = []

        for address, name in newDevs:
            stmts.append((ROOM['bluetooth'],
                          ROOM['senses'],
                          Literal(str(address))))
            if address not in prevDevs:
                matches = 0
                for dev in devicesFromAddress(address):
                    log.info("found %s" % dev)
                    matches += 1
                if not matches:
                    log.info("no matches for %s (%s)" % (name, address))

                    print "%s %s %s" % (time.time(), name, address)

                self.lastNameForAddress[address] = name
                print 'mongoInsert', ({"sensor" : "bluetooth",
                             "address" : address,
                             "name" : name,
                             "action" : "arrive"})

            lostDevs.discard(address)
            self.lastDevs.add(address)

        for address in lostDevs:
            print 'mongoInsert', ({"sensor" : "bluetooth",
                         "address" : address,
                         "name" : self.lastNameForAddress[address],
                         "action" : "leave"})

            for dev in devicesFromAddress(address):
                log.info("lost %s" % dev)

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        age = time.time() - self.settings.poller.lastPollTime
        if age > 60 + 30:
            raise ValueError("poll data is stale. age=%s" % age)
        
        self.write("bluetooth watcher. ")

if __name__ == '__main__':
    log.setLevel(logging.DEBUG)
    poller = Poller()
    reactor.listenTCP(9077, cyclone.web.Application([
        (r'/', Index),
        ], poller=poller))
    task.LoopingCall(poller.poll).start(1)
    reactor.run()
