"""
see ./reasoning for usage
"""

import sys, os
try:
    from rdflib.Graph import Graph
except ImportError:
    from rdflib import Graph
    
from rdflib.parser import StringInputSource

sys.path.append("/my/proj/room/fuxi/build/lib.linux-x86_64-2.6")
from FuXi.Rete.Util import generateTokenSet
from FuXi.Rete import ReteNetwork
from FuXi.Rete.RuleStore import N3RuleStore

from rdflib import plugin, Namespace
from rdflib.store import Store

sys.path.append('../../../ffg/ffg')
import evtiming

from escapeoutputstatements import escapeOutputStatements
ROOM = Namespace("http://projects.bigasterisk.com/room/")

_rulesCache = (None, None, None, None)
@evtiming.serviceLevel.timed('readRules')
def readRules(rulesPath, outputPatterns):
    """
    returns (rulesN3, ruleGraph)

    This includes escaping certain statements in the output
    (implied) subgraaphs so they're not confused with input
    statements.
    """
    global _rulesCache
    mtime = os.path.getmtime(rulesPath)
    key = (rulesPath, mtime)
    if _rulesCache[:2] == key:
        _, _, rulesN3, expandedN3 = _rulesCache
    else:
        rulesN3 = open(rulesPath).read() # for web display

        plainGraph = Graph()
        plainGraph.parse(StringInputSource(rulesN3),
                         format='n3') # for inference
        escapeOutputStatements(plainGraph, outputPatterns=outputPatterns)
        expandedN3 = plainGraph.serialize(format='n3')
        _rulesCache = key + (rulesN3, expandedN3)

    # the rest needs to happen each time since inference is
    # consuming the ruleGraph somehow
    ruleStore = N3RuleStore()
    ruleGraph = Graph(ruleStore)

    ruleGraph.parse(StringInputSource(expandedN3), format='n3')
    log.debug('%s rules' % len(ruleStore.rules))
    return rulesN3, ruleGraph

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
