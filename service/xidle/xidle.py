#!bin/python
from __future__ import division
"""
X server idle time is now available over http!

Note: HD-4110 webcams stop X from going idle by sending events
constantly. Run this to fix:

    xinput disable "HP Webcam HD-4110"
"""

import time
import sys, socket, json, os
from rdflib import Namespace, URIRef, Literal
from influxdb import InfluxDBClient
import influxdb.exceptions
import cyclone.web
from twisted.internet import reactor, task

import actmon
# another option: http://thp.io/2007/09/x11-idle-time-and-focused-window-in.html

DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

sys.path.append('../../lib')
from patchablegraph import PatchableGraph, CycloneGraphEventsHandler, CycloneGraphHandler

host = socket.gethostname()
client = InfluxDBClient('bang6', 9060, 'root', 'root', 'main')

class Root(cyclone.web.RequestHandler):
    def get(self):
        xss.get_info() # fail if we can't get the display or something
        self.write('''
      Get the <a href="idle">X idle time</a> on %s.
      <a href="graph">rdf graph</a> available.''' % host)
        
class Idle(cyclone.web.RequestHandler):
    def get(self):
        self.set_header('Content-type', 'application/json')
        self.write(json.dumps({"idleMs" : xss.get_info().idle}))
        
class Graph(cyclone.web.RequestHandler):
    def get(self):
        self.set_header('Content-type', 'application/x-trig')

        g = StateGraph(ctx=DEV['xidle/%s' % host])

        ms = xss.get_info().idle
        subj = URIRef("http://bigasterisk.com/host/%s/xidle" % host)
        g.add((subj, ROOM['idleTimeMs'], Literal(ms)))
        g.add((subj, ROOM['idleTimeMinutes'], Literal(ms / 1000 / 60)))

        self.write(g.asTrig())

class Poller(object):
    def __init__(self):
        self.points = []
        self.lastSent = None
        self.lastSentTime = 0
        task.LoopingCall(self.poll).start(5)
        
    def poll(self):
        ms = xss.get_info().idle
        lastMinActive = ms < 60 * 1000
        now = int(time.time())
        if self.lastSent != lastMinActive or now > self.lastSentTime + 3600:
            self.points.append({"measurement": "presence",
                                "tags": {"host": host, "sensor": "xidle"},
                                "fields": {"value": 1 if lastMinActive else 0},
                                "time": now})
            self.lastSent = lastMinActive
            self.lastSentTime = now

            client.write_points(self.points, time_precision='s')
            self.points = []

poller = Poller()
            
reactor.listenTCP(9107, cyclone.web.Application([
    (r'/', Root),
    (r'/idle', Idle),
    (r'/graph', Graph),
]), interface='::')

reactor.run()
