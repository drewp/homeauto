#!/usr/bin/python
"""
return some rdf about the environment, e.g. the current time,
daytime/night, overall modes like 'maintenance mode', etc

"""
import sys, datetime, cyclone.web
from twisted.internet import reactor
from dateutil.tz import tzlocal
from rdflib import Namespace, Literal
sys.path.append("/my/site/magma")
from stategraph import StateGraph
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.write('this is envgraph: <a href="graph">rdf</a>')
        
class GraphHandler(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        g = StateGraph(ROOM.environment)
        now = datetime.datetime.now(tzlocal())

        g.add((DEV.environment, ROOM.localHour, Literal(now.hour)))
        
        self.set_header('Content-type', 'application/x-trig')
        self.write(g.asTrig())
        
class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/", Index),
            (r'/graph', GraphHandler),
        ]
        cyclone.web.Application.__init__(self, handlers)

if __name__ == '__main__':
    reactor.listenTCP(9075, Application())
    reactor.run()
