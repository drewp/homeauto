import time
import requests
from rdflib import ConjunctiveGraph
        
def addTrig(graph, url, timeout=2):
    t1 = time.time()
    response = requests.get(url, stream=True, timeout=timeout)
    if response.status_code != 200:
        raise ValueError("status %s from %s" % (response.status, url))
    g = ConjunctiveGraph()
    g.parse(response.raw, format='trig')
    fetchTime = time.time() - t1
    graph.addN(g.quads())
    return fetchTime
