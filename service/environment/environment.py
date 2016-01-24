#!/usr/bin/python
"""
return some rdf about the environment, e.g. the current time,
daytime/night, overall modes like 'maintenance mode', etc

"""
import sys, datetime, cyclone.web
from twisted.internet import reactor, task
from dateutil.tz import tzlocal
from dateutil.relativedelta import relativedelta, FR
from rdflib import Namespace, Literal
sys.path.append("/my/proj/homeauto/lib")
from patchablegraph import PatchableGraph, writeGraphResponse, GraphEventsHandler
from cycloneerr import PrettyErrorHandler
from twilight import isWithinTwilight

from rdfdoc import Doc

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")


class GraphHandler(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        writeGraphResponse(self, self.settings.masterGraph,
                           self.request.headers.get('accept'))

def update(masterGraph):
    stmt = lambda s, p, o: masterGraph.patchObject(ROOM.environment, s, p, o)
    
    now = datetime.datetime.now(tzlocal())

    stmt(DEV.environment, ROOM.localHour, Literal(now.hour))
    stmt(DEV.environment, ROOM.localTimeToMinute,
         Literal(now.strftime("%H:%M")))

    stmt(DEV.environment, ROOM.localTimeToSecond,
         Literal(now.strftime("%H:%M:%S")))

    stmt(DEV.environment, ROOM.localDayOfWeek,
         Literal(now.strftime("%A")))
    stmt(DEV.environment, ROOM.localMonthDay,
         Literal(now.strftime("%B %e")))
    stmt(DEV.environment, ROOM.localDate,
         Literal(now.strftime("%Y-%m-%d")))

    for offset in range(-12, 7):
        d = now.date() + datetime.timedelta(days=offset)
        if d == d + relativedelta(day=31, weekday=FR(-1)):
            stmt(DEV.calendar, ROOM.daysToLastFridayOfMonth, Literal(offset))

    stmt(DEV.calendar, ROOM.twilight,
         ROOM['withinTwilight'] if isWithinTwilight(now) else ROOM['daytime'])

       
def main():
    from twisted.python import log as twlog
    twlog.startLogging(sys.stderr)
    masterGraph = PatchableGraph()

    class Application(cyclone.web.Application):
        def __init__(self):
            handlers = [
                (r"/()", cyclone.web.StaticFileHandler,
                 {"path": ".", "default_filename": "index.html"}),
                (r'/graph', GraphHandler),
                (r'/graph/events', GraphEventsHandler),
                (r'/doc', Doc), # to be shared
            ]
            cyclone.web.Application.__init__(self, handlers,
                                             masterGraph=masterGraph)
    task.LoopingCall(update, masterGraph).start(1)
    reactor.listenTCP(9075, Application())
    reactor.run()

if __name__ == '__main__':
    main()
    
