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
        g.add((DEV.environment, ROOM.localDayOfWeek,
               Literal(now.strftime("%A"))))
        g.add((DEV.environment, ROOM.localMonthDay,
               Literal(now.strftime("%B %e"))))
        g.add((DEV.environment, ROOM.localDate,
               Literal(now.strftime("%Y-%m-%d"))))

        for offset in range(-12, 7):
            d = now.date() + datetime.timedelta(days=offset)
            if d == d + relativedelta(day=31, weekday=FR(-1)):
                g.add((DEV.calendar, ROOM.daysToLastFridayOfMonth,
                       Literal(offset)))

        g.add((DEV.calendar, ROOM.twilight,
               ROOM['withinTwilight'] if isWithinTwilight(now) else
               ROOM['daytime']))

        ct, body = g.asAccepted(self.request.headers.get('accept'))
        self.set_header('Content-type', ct)
        self.write(body)

from rdfdoc import Doc
        
class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/()", cyclone.web.StaticFileHandler,
             {"path": ".", "default_filename": "index.html"}),
            (r'/graph', GraphHandler),
            (r'/doc', Doc), # to be shared
        ]
        cyclone.web.Application.__init__(self, handlers)

if __name__ == '__main__':
    reactor.listenTCP(9075, Application())
    reactor.run()
