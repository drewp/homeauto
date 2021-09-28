#!bin/python

"""
may need this:
ps axf | grep /run/gdm
18339 tty7     Ss+    0:00      \_ /usr/bin/X :0 -background none -verbose -auth /run/gdm/auth-for-gdm-iQoCDZ/database -nolisten tcp vt7
eval xauth add `sudo xauth -f /run/gdm/auth-for-gdm-iQoCDZ/database list :0`

"""

from twisted.internet import reactor, task
import cyclone.web
from influxdb import InfluxDBClient
import subprocess, sys, socket, time, os
from rdflib import Namespace, URIRef
from standardservice.logsetup import log, verboseLogging
from cycloneerr import PrettyErrorHandler
import dpms

DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

from patchablegraph import PatchableGraph, CycloneGraphEventsHandler, CycloneGraphHandler

influx = InfluxDBClient('bang6', 9060, 'root', 'root', 'main')

host = socket.gethostname()

os.environ['DISPLAY'] = ':0.0'
d = dpms.DPMS()


def getMonitorState():
    return 'on' if d.Info()[0] == dpms.DPMSModeOn else 'off'

class Root(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        getMonitorState() # to make it fail if xset isn't working
        self.set_header('content-type', 'text/html')
        self.write('''
        <!doctype html>
<html>
  <head>
    <title>dpms</title>
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

      Get and put the <a href="monitor">monitor power</a> with dpms.

      <streamed-graph url="graph/dpms/events" graph="{{graph}}"></streamed-graph>
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
        <a href="monitor">/monitor (put)</a>
    </div>

  </body>
</html>
''')


class Monitor(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header('content-type', 'text/plain')
        self.write(getMonitorState())

    def put(self):
        body = self.request.body.decode('ascii').strip()
        if body not in ['on', 'off']:
            raise NotImplementedError("body must be 'on' or 'off'")
        d.ForceLevel(dpms.DPMSModeOff if body == 'off' else dpms.DPMSModeOn)
        self.set_status(204)

class Poller(object):
    def __init__(self):
        self.lastSent = None
        self.lastSentTime = 0
        task.LoopingCall(self.poll).start(5)

    def poll(self):
        now = int(time.time())
        state = getMonitorState()

        ctx=DEV['dpms/%s' % host]
        masterGraph.patchObject(
            ctx,
            URIRef("http://bigasterisk.com/host/%s/monitor" % host),
            ROOM['powerStateMeasured'],
            ROOM[getMonitorState()])

        if state != self.lastSent or (now > self.lastSentTime + 3600):
            influx.write_points([
                {'measurement': 'power',
                 'tags': {'device': '%sMonitor' % host},
                 'fields': {'value': 1 if state == 'on' else 0},
                 'time': now
                 }], time_precision='s')

            self.lastSent = state
            self.lastSentTime = now

verboseLogging(False)

masterGraph = PatchableGraph()
poller = Poller()

reactor.listenTCP(9095, cyclone.web.Application([
    (r'/', Root),
    (r'/monitor', Monitor),
    (r'/graph/dpms', CycloneGraphHandler, {'masterGraph': masterGraph}),
    (r'/graph/dpms/events', CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
]), interface='::')

reactor.run()
