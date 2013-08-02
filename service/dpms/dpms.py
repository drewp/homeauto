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

from bottle import run, get, put, request, response
import subprocess, sys, socket
from rdflib import Namespace, URIRef
DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

sys.path.append("/my/site/magma")
from stategraph import StateGraph
sys.path.append("../../lib")
from localdisplay import setDisplayToLocalX

def getMonitorState():
    out = subprocess.check_output(['xset', 'q'])
    for line in out.splitlines():
        line = line.strip()
        if line == 'Monitor is On':
            response.set_header('content-type', 'text/plain')
            return 'on'
        elif line in ['Monitor is Off', 'Monitor is in Suspend', 'Monitor is in Standby']:
            response.set_header('content-type', 'text/plain')
            return 'off'
    raise NotImplementedError("no matching monitor line in xset output")

@get("/")
def index():
    getMonitorState() # to make it fail if xset isn't working
    return '''
      Get and put the <a href="monitor">monitor power</a> with dpms.
      <a href="graph">rdf graph</a> available.'''
    
@get("/monitor")
def monitor():
    return getMonitorState()

@put("/monitor")
def putMonitor():
    body = request.body.read().strip()
    if body in ['on', 'off']:
        subprocess.check_call(['xset', 'dpms', 'force', body])
        response.status = 204
    else:
        raise NotImplementedError("body must be 'on' or 'off'")
    return ''

@get("/graph")
def graph():
    host = socket.gethostname()
    g = StateGraph(ctx=DEV['dpms/%s' % host])
    g.add((URIRef("http://bigasterisk.com/host/%s/monitor" % host),
           ROOM['powerStateMeasured'],
           ROOM[getMonitorState()]))
    
    response.set_header('Content-type', 'application/x-trig')
    return g.asTrig()

setDisplayToLocalX()

run(host="0.0.0.0", server='gunicorn', port=9095, quiet=True)

