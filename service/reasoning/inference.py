"""
see ./reasoning for usage
"""

import sys, re
import restkit
from rdflib import StringInputSource, URIRef
from rdflib.Graph import Graph

sys.path.append("/my/proj/room/fuxi/build/lib.linux-x86_64-2.6")
from FuXi.Rete.Util import generateTokenSet
from FuXi.Rete import ReteNetwork
from rdflib import plugin
from rdflib.store import Store

def parseTrig(trig):
    """
    yields quads
    """
    m = re.match(r"<([^>]+)> \{(.*)\}\s*$", trig, re.DOTALL)
    if m is None:
        raise NotImplementedError("trig format was too tricky: %r..." % trig[:200])
        
    ctx = URIRef(m.group(1))
    n3 = m.group(2)
    g = Graph()
    g.parse(StringInputSource(n3), format="n3")
    for stmt in g:
        yield stmt + (ctx,)

def infer(graph, rules):
    """
    returns new graph of inferred statements
    """
    # based on fuxi/tools/rdfpipe.py
    store = plugin.get('IOMemory',Store)()        
    store.open('')

    target = Graph()
    tokenSet = generateTokenSet(graph)
    network = ReteNetwork(rules, inferredTarget=target)
    network.feedFactsToAdd(tokenSet)

    store.rollback()
    return target

import time, logging
log = logging.getLogger()
def logTime(func):
    def inner(*args, **kw):
        t1 = time.time()
        try:
            ret = func(*args, **kw)
        finally:
            log.info("Call to %s took %.1f ms" % (
                func.__name__, 1000 * (time.time() - t1)))
        return ret
    return inner

def addTrig(graph, url):
    trig = restkit.request(url).body_string()
    graph.addN(parseTrig(trig))
