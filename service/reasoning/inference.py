"""
see ./reasoning for usage
"""

import sys, os, contextlib
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

from greplin import scales 
STATS = scales.collection('/web',
                          scales.PmfStat('readRules'))

from escapeoutputstatements import escapeOutputStatements
ROOM = Namespace("http://projects.bigasterisk.com/room/")

def _loadAndEscape(ruleStore, n3, outputPatterns):
    ruleGraph = Graph(ruleStore)

    # Can't escapeOutputStatements in the ruleStore since it
    # doesn't support removals. Can't copy plainGraph into
    # ruleGraph since something went wrong with traversing the
    # triples inside quoted graphs, and I lose all the bodies
    # of my rules. This serialize/parse version is very slow (400ms),
    # but it only runs when the file changes.
    plainGraph = Graph()
    plainGraph.parse(StringInputSource(n3), format='n3') # for inference
    escapeOutputStatements(plainGraph, outputPatterns=outputPatterns)
    expandedN3 = plainGraph.serialize(format='n3')

    ruleGraph.parse(StringInputSource(expandedN3), format='n3')

_rulesCache = (None, None, None, None)
def readRules(rulesPath, outputPatterns):
    """
    returns (rulesN3, ruleStore)

    This includes escaping certain statements in the output
    (implied) subgraaphs so they're not confused with input
    statements.
    """
    global _rulesCache

    with STATS.readRules.time():
        mtime = os.path.getmtime(rulesPath)
        key = (rulesPath, mtime)
        if _rulesCache[:2] == key:
            _, _, rulesN3, ruleStore = _rulesCache
        else:
            rulesN3 = open(rulesPath).read() # for web display

            ruleStore = N3RuleStore()
            _loadAndEscape(ruleStore, rulesN3, outputPatterns)
            log.debug('%s rules' % len(ruleStore.rules))
            
            _rulesCache = key + (rulesN3, ruleStore)
        return rulesN3, ruleStore

def infer(graph, rules):
    """
    returns new graph of inferred statements. Plain rete api seems to
    alter rules.formulae and rules.rules, but this function does not
    alter the incoming rules object, so you can cache it.
    """
    # based on fuxi/tools/rdfpipe.py
    target = Graph()
    tokenSet = generateTokenSet(graph)
    with _dontChangeRulesStore(rules):
        network = ReteNetwork(rules, inferredTarget=target)
        network.feedFactsToAdd(tokenSet)
    
    return target

@contextlib.contextmanager
def _dontChangeRulesStore(rules):
    if not hasattr(rules, '_stashOriginalRules'):
        rules._stashOriginalRules = rules.rules[:]
    yield
    for k in rules.formulae.keys():
        if not k.startswith('_:Formula'):
            del rules.formulae[k]
    rules.rules = rules._stashOriginalRules[:]
    
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
