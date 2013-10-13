#!/usr/bin/python
"""
return some rdf about the environment, e.g. the current time,
daytime/night, overall modes like 'maintenance mode', etc

"""
import sys, datetime, cyclone.web
from twisted.internet import reactor
from dateutil.tz import tzlocal
from dateutil.relativedelta import relativedelta, FR
from rdflib import Namespace, Literal
sys.path.append("/my/site/magma")
from stategraph import StateGraph
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from twilight import isWithinTwilight

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")

class GraphHandler(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        g = StateGraph(ROOM.environment)
        now = datetime.datetime.now(tzlocal())

        g.add((DEV.environment, ROOM.localHour, Literal(now.hour)))
        g.add((DEV.environment, ROOM.localTimeToMinute,
               Literal(now.strftime("%H:%M"))))
        g.add((DEV.environment, ROOM.localTimeToSecond,
               Literal(now.strftime("%H:%M:%S"))))

        for offset in range(-12, 7):
            d = now.date() + datetime.timedelta(days=offset)
            if d == d + relativedelta(day=31, weekday=FR(-1)):
                g.add((DEV.calendar, ROOM.daysToLastFridayOfMonth,
                       Literal(offset)))

        g.add((DEV.calendar, ROOM.twilight,
               ROOM['withinTwilight'] if isWithinTwilight(now) else
               ROOM['daytime']))
        
        self.set_header('Content-type', 'application/x-trig')
        self.write(g.asTrig())
        
class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/()", cyclone.web.StaticFileHandler,
             {"path": ".", "default_filename": "index.html"}),
            (r'/graph', GraphHandler),
        ]
        cyclone.web.Application.__init__(self, handlers)

if __name__ == '__main__':
    reactor.listenTCP(9075, Application())
    reactor.run()
