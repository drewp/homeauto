#!bin/python

"""
X server idle time is now available over http!
"""

from bottle import run, get, put, request, response
import subprocess, sys, socket
from rdflib import Namespace, URIRef, Literal

# from http://bebop.bigasterisk.com/python/
import xss
# another option: http://thp.io/2007/09/x11-idle-time-and-focused-window-in.html

DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

sys.path.append("/my/site/magma")
from stategraph import StateGraph

host = socket.gethostname()

@get("/")
def index():
    xss.get_info() # fail if we can't get the display or something
    return '''
      Get the <a href="idle">X idle time</a> on %s.
      <a href="graph">rdf graph</a> available.''' % host

@get("/idle")
def monitor():
    return {"idleMs" : xss.get_info().idle}

@get("/graph")
def graph():
    g = StateGraph(ctx=DEV['xidle/%s' % host])
    g.add((URIRef("http://bigasterisk.com/host/%s/xidle" % host),
           ROOM['idleTimeMs'],
           Literal(xss.get_info().idle)))

    response.set_header('Content-type', 'application/x-trig')
    return g.asTrig()

run(host="0.0.0.0", server='gunicorn', port=9107, quiet=True)

