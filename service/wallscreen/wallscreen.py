"""
for raspberry pi screen.
  B2G_HOMESCREEN=http://10.1.0.1:9102 b2g/b2g --screen=700x480
and then fix the window with this:
  echo "window.resizeTo(702,480)" | nc localhost 9999
"""
import bottle, json, pystache, restkit
from dateutil.parser import parse
from rdflib import Graph, URIRef, Namespace, Literal, RDF
CV = Namespace("http://bigasterisk.com/checkvist/v1#")
EV = Namespace("http://bigasterisk.com/event#")

@bottle.route('/')
def index():
    return pystache.render(open("vist.html").read())

@bottle.route("/content")
def content():

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
        
    return {'tasks':out, 'events' : events}

@bottle.route("/thermostat")
def thermostat():
    return restkit.request("http://bang:10001/requestedTemperature").body_string()
    
    
@bottle.route('/static/<path:path>')
def server_static(path):
    return bottle.static_file(path, root='static')

bottle.run(host="0.0.0.0", port=9102)
