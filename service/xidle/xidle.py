"""
X server idle time is now available over http!

Note: HD-4110 webcams stop X from going idle by sending events
constantly. Run this to fix:

    xinput disable "HP Webcam HD-4110"
"""
import time
import socket, json, os
from rdflib import Namespace, URIRef, Literal
from influxdb import InfluxDBClient
import influxdb.exceptions
import cyclone.web
from twisted.internet import reactor, task
from standardservice.logsetup import log, verboseLogging
from patchablegraph import PatchableGraph, CycloneGraphEventsHandler, CycloneGraphHandler

DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

host = socket.gethostname()
client = InfluxDBClient('bang6', 9060, 'root', 'root', 'main')

os.environ['DISPLAY'] = ':0.0'

import pxss
# another option: http://thp.io/2007/09/x11-idle-time-and-focused-window-in.html

def get_idle_time():
    return pxss.get_info().idle

get_idle_time() # fail if we can't get the display or something

class Root(cyclone.web.RequestHandler):
    def get(self):
        get_idle_time() # fail if we can't get the display or something
        self.set_header('content-type', 'text/html')
        self.write('''
        <!doctype html>
<html>
  <head>
    <title>xidle</title>
    <meta charset="utf-8" />
    <script src="/lib/polymer/1.0.9/webcomponentsjs/webcomponents.min.js"></script>
    <script src="/lib/require/require-2.3.3.js"></script>
    <script src="/rdf/common_paths_and_ns.js"></script>

    <link rel="import" href="/rdf/streamed-graph.html">
    <link rel="import" href="/lib/polymer/1.0.9/polymer/polymer.html">

    <meta name="mobile-web-app-capable" content="yes">
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body>
    <template id="t" is="dom-bind">

      Get the <a href="idle">X idle time</a> on %s.

      <streamed-graph url="graph/xidle/events" graph="{{graph}}"></streamed-graph>
      <div id="out"></div>
      <script type="module" src="/rdf/streamed_graph_view.js"></script>
    </template>
    <style>
     .served-resources {
         margin-top: 4em;
         border-top: 1px solid gray;
         padding-top: 1em;
     }
     .served-resources a {
         padding-right: 2em;
     }
    </style>

      <div class="served-resources">
        <a href="stats/">/stats/</a>
        <a href="graph/dpms">/graph/dpms</a>
        <a href="graph/dpms/events">/graph/dpms/events</a>
        <a href="idle">/idle</a>
    </div>

  </body>
</html>
        ''' % host)

class Idle(cyclone.web.RequestHandler):
    def get(self):
        self.set_header('Content-type', 'application/json')
        self.write(json.dumps({"idleMs" : get_idle_time()}))

class Poller(object):
    def __init__(self):
        self.points = []
        self.lastSent = None
        self.lastSentTime = 0
        self.lastGraphSent = None
        self.lastGraphSentTime = 0
        task.LoopingCall(self.poll).start(1)

    def poll(self):
        ms = get_idle_time()
        ctx = DEV['xidle/%s' % host]
        subj = URIRef("http://bigasterisk.com/host/%s/xidle" % host)
        lastMinActive = ms < 60 * 1000
        now = int(time.time())

        nextGraphUpdate = self.lastGraphSentTime + min(10, ms / 1000 / 2)
        if self.lastGraphSent != lastMinActive or now > nextGraphUpdate:
            masterGraph.patchObject(ctx, subj, ROOM['idleTimeMs'], Literal(ms))
            masterGraph.patchObject(ctx, subj, ROOM['idleTimeMinutes'],
                                    Literal(round(ms / 1000 / 60, 2)))
            self.lastGraphSent = lastMinActive
            self.lastGraphSentTime = now

        if self.lastSent != lastMinActive or now > self.lastSentTime + 3600:
            self.points.append({"measurement": "presence",
                                "tags": {"host": host, "sensor": "xidle"},
                                "fields": {"value": 1 if lastMinActive else 0},
                                "time": now})
            self.lastSent = lastMinActive
            self.lastSentTime = now

            try:
                client.write_points(self.points, time_precision='s')
            except influxdb.exceptions.InfluxDBServerError as e:
                log.error(repr(e))
                reactor.crash()
            self.points = []

verboseLogging(False)

masterGraph = PatchableGraph()
poller = Poller()

reactor.listenTCP(9107, cyclone.web.Application([
    (r'/', Root),
    (r'/idle', Idle),
    (r'/graph/xidle', CycloneGraphHandler, {'masterGraph': masterGraph}),
    (r'/graph/xidle/events', CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
]), interface='::')

reactor.run()
