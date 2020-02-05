#!bin/python

"""
sample supervisord block

[program:dpms_9095]
directory=/my/proj/homeauto/service/dpms
command=/my/proj/homeauto/service/dpms/bin/python dpms.py
user=drewp

On one box, this goes super slow when avahi daemon is running. Maybe
it's for an attempted dns lookup of the requesting IP address, which I
wish I could switch off.

--

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
from logsetup import log, enableTwistedLog

from dpms import DPMS, DPMSModeOn
DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

sys.path.append("/my/site/magma")
from patchablegraph import PatchableGraph, CycloneGraphEventsHandler, CycloneGraphHandler
#sys.path.append("../../lib")
#from localdisplay import setDisplayToLocalX

influx = InfluxDBClient('bang6', 9060, 'root', 'root', 'main')

os.environ['DISPLAY'] = ':0.0'

dpms = DPMS()
host = socket.gethostname()

def getMonitorState():
    level, enabled = dpms.Info()
    return 'on' if level == DPMSModeOn else 'off'

class Root(cyclone.web.RequestHandler):
    def get(self):
        getMonitorState() # to make it fail if xset isn't working
        self.write('''
          Get and put the <a href="monitor">monitor power</a> with dpms.
          <a href="graph">rdf graph</a> available.''')
    
class Monitor(cyclone.web.RequestHandler):
    def get(self):
        self.set_header('content-type', 'text/plain')
        self.write(getMonitorState())

    def put(self):
        body = self.request.body.strip()
        if body in ['on', 'off']:
            subprocess.check_call(['xset', 'dpms', 'force', body])
            self.set_status(204)
        else:
            raise NotImplementedError("body must be 'on' or 'off'")

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

masterGraph = PatchableGraph()
poller = Poller()

reactor.listenTCP(9095, cyclone.web.Application([
    (r'/', Root),
    (r'/monitor', Monitor),
    (r'/graph/dpms', CycloneGraphHandler, {'masterGraph': masterGraph}),
    (r'/graph/dpms/events', CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
]), interface='::')

reactor.run()
