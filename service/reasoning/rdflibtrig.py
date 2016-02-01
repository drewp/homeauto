import re, time
import restkit
from rdflib.parser import StringInputSource
from rdflib import ConjunctiveGraph
        
def addTrig(graph, url, timeout=2):
    t1 = time.time()
    response = restkit.request(url, timeout=timeout)
    if response.status_int != 200:
        raise ValueError("status %s from %s" % (response.status, url))
    trig = response.body_string()
    fetchTime = time.time() - t1
    g = ConjunctiveGraph()
    g.parse(StringInputSource(trig), format='trig')
    graph.addN(g.quads())
    return fetchTime
