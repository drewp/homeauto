"""
see ./reasoning for usage
"""

import sys
try:
    from rdflib import StringInputSource
    from rdflib.Graph import Graph
except ImportError:
    from rdflib.parser import StringInputSource
    from rdflib import Graph

sys.path.append("/my/proj/room/fuxi/build/lib.linux-x86_64-2.6")
from FuXi.Rete.Util import generateTokenSet
from FuXi.Rete import ReteNetwork
from rdflib import plugin
from rdflib.store import Store
from rdflibtrig import parseTrig, addTrig

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
