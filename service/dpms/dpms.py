#!bin/python

"""
sample supervisord block

[program:dpms_9095]
directory=/my/proj/homeauto/service/dpms
command=/my/proj/homeauto/service/dpms/bin/python dpms.py
environment=DISPLAY=:0.0
user=drewp

On one box, this goes super slow when avahi daemon is running. Maybe
it's for an attempted dns lookup of the requesting IP address, which I
wish I could switch off.

"""

from bottle import run, get, put, request, response
import subprocess, sys, socket
from rdflib import Namespace, URIRef
DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

sys.path.append("/my/site/magma")
from stategraph import StateGraph

def getMonitorState():
    out = subprocess.check_output(['xset', 'q'])
    for line in out.splitlines():
        line = line.strip()
        if line == 'Monitor is On':
            response.set_header('content-type', 'text/plain')
            return 'on'
        elif line == 'Monitor is Off':
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
           ROOM['powerState'],
           ROOM[getMonitorState()]))
    
    response.set_header('Content-type', 'application/x-trig')
    return g.asTrig()
    
run(host="0.0.0.0", port=9095, quiet=True)

