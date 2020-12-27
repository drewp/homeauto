"""
see ./reasoning for usage
"""

import contextlib
import os

from prometheus_client import Summary
from rdflib import Graph, Namespace
from rdflib.graph import ConjunctiveGraph
from rdflib.parser import StringInputSource

from escapeoutputstatements import escapeOutputStatements

READ_RULES_CALLS = Summary('read_rules_calls', 'calls')

ROOM = Namespace("http://projects.bigasterisk.com/room/")
LOG = Namespace('http://www.w3.org/2000/10/swap/log#')


def _loadAndEscape(ruleStore: ConjunctiveGraph, n3: bytes, outputPatterns):
    ruleStore.parse(StringInputSource(n3), format='n3')
    return
    ruleGraph = Graph(ruleStore)

    # Can't escapeOutputStatements in the ruleStore since it
    # doesn't support removals. Can't copy plainGraph into
    # ruleGraph since something went wrong with traversing the
    # triples inside quoted graphs, and I lose all the bodies
    # of my rules. This serialize/parse version is very slow (400ms),
    # but it only runs when the file changes.
    plainGraph = Graph()
    plainGraph.parse(StringInputSource(n3.encode('utf8')), format='n3')  # for inference
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

    with READ_RULES_CALLS.time():
        mtime = os.path.getmtime(rulesPath)
        key = (rulesPath, mtime)
        if _rulesCache[:2] == key:
            _, _, rulesN3, ruleStore = _rulesCache
        else:
            rulesN3 = open(rulesPath, 'rb').read()  # for web display

            ruleStore = ConjunctiveGraph()
            _loadAndEscape(ruleStore, rulesN3, outputPatterns)
            log.debug('%s rules' % len(ruleStore))

            _rulesCache = key + (rulesN3, ruleStore)
        return rulesN3, ruleStore


def infer(graph: ConjunctiveGraph, rules: ConjunctiveGraph):
    """
    returns new graph of inferred statements.
    """
    log.info(f'Begin inference of graph len={len(graph)} with rules len={len(rules)}:')

    workingSet = ConjunctiveGraph()
    workingSet.addN(graph.quads())

    implied = ConjunctiveGraph()

    delta = 1
    while delta > 0:
        delta = -len(implied)

        for r in rules:
            if r[1] == LOG['implies']:
                containsSetup = all(st in workingSet for st in r[0])
                if containsSetup:
                    log.info(f'  Rule {r[0]} -> present={containsSetup}')
                    for st in r[0]:
                        log.info(f'     {st[0].n3()} {st[1].n3()} {st[2].n3()}')

                    log.info(f'  ...implies {len(r[2])} statements')
                if containsSetup:
                    for st in r[2]:
                        workingSet.add(st)
                        implied.add(st)
            else:
                log.info(f'  {r}')
        delta += len(implied)
        log.info(f'  this inference round added {delta} more implied stmts')
    log.info(f'{len(implied)} stmts implied:')
    for st in implied:
        log.info(f'  {st}')
    return implied

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
    for k in list(rules.formulae.keys()):
        if not k.startswith('_:Formula'):
            del rules.formulae[k]
    rules.rules = rules._stashOriginalRules[:]


import logging
import time

log = logging.getLogger()


def logTime(func):

    def inner(*args, **kw):
        t1 = time.time()
        try:
            ret = func(*args, **kw)
        finally:
            log.info("Call to %s took %.1f ms" % (func.__name__, 1000 * (time.time() - t1)))
        return ret

    return inner
