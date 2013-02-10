"""
for raspberry pi screen.
  B2G_HOMESCREEN=http://10.1.0.1:9102 b2g/b2g --screen=700x480
and then fix the window with this:
  echo "window.resizeTo(702,480)" | nc localhost 9999
"""
import json, sys
from dateutil.parser import parse
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
import cyclone.web, cyclone.httpclient, cyclone.websocket
from rdflib import Graph, URIRef, Namespace, Literal, RDF

sys.path.append("../../lib")
from logsetup import log
from cycloneerr import PrettyErrorHandler

CV = Namespace("http://bigasterisk.com/checkvist/v1#")
EV = Namespace("http://bigasterisk.com/event#")

class Content(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        out = []
        if 0: # needs to be rewritten for trello
            g = Graph()
            g.parse("http://bang:9103/graph", format="n3")

            tasks = [] # (pos, task)
            for t in g.subjects(RDF.type, CV.OpenTask):
                if (None, CV.child, t) in g:
                    continue
                tasks.append((g.value(t, CV.position), t))
            tasks.sort()

            def appendTree(t, depth):
                out.append(dict(
                    uri=t,
                    depth=depth,
                    mark=g.value(t, CV.mark),
                    content=g.value(t, CV.content),
                    ))
                for sub in g.objects(t, CV.child):
                    if (sub, RDF.type, CV.OpenTask) not in g:
                        continue
                    appendTree(sub, depth+1)

            for pos, t in tasks[:10]:
                appendTree(t, depth=0)

        events = [] # [{'date':'yyyy-mm-dd', 'dayEvents':[], 'timeEvents':[]}]
        g = Graph()
        g.parse("http://bang:9105/events?days=3", format='n3')
        byDay = {}
        for ev in g.subjects(RDF.type, EV.Event):
            start = g.value(ev, EV['start'])
            s = parse(start)
            d = s.date().isoformat()
            byDay.setdefault(d, {'dayEvents':[],
                                 'timeEvents':[]})[
                'timeEvents' if 'T' in start else 'dayEvents'].append({
                'title' : g.value(ev, EV['title']),
                'start' : start,
                'date' : s.date().isoformat(),
                'time' : s.time().isoformat()[:-3],
                })
        for k,v in sorted(byDay.items(), key=lambda (k,v): k):
            d = {'date':k, 'weekdayName':parse(k).strftime("%A")}
            d.update(v)
            d['dayEvents'].sort(key=lambda ev: ev['title'])
            d['timeEvents'].sort(key=lambda ev: ev['start'])
            events.append(d)

        self.write(json.dumps({'tasks':out, 'events' : events}))

class Thermostat(PrettyErrorHandler, cyclone.web.RequestHandler):
    @inlineCallbacks
    def get(self):
        self.write((yield cyclone.httpclient.fetch("http://bang:10001/requestedTemperature")).body)
    
    
if __name__ == '__main__':
    from twisted.python import log as twlog
    #twlog.startLogging(sys.stdout)
            
    port = 9102
    reactor.listenTCP(port, cyclone.web.Application(handlers=[
        (r'/content', Content),
        (r'/thermostat', Thermostat),        
        (r'/(.*)', cyclone.web.StaticFileHandler,
         {"path" : ".", # security hole- serves this dir too
          "default_filename" : "index.html"}),
        ]))
    log.info("serving on %s" % port)
    reactor.run()
