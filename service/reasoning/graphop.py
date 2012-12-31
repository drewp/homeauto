import logging
from rdflib import URIRef, ConjunctiveGraph
log = logging.getLogger()

def graphWithoutMetadata(g, ignorePredicates=[]):
    """
    graph filter that removes any statements whose subjects are
    contexts in the graph and also any statements with the given
    predicates
    """
    ctxs = map(URIRef, set(g.contexts())) # weird they turned to strings

    out = ConjunctiveGraph()
    for stmt in g.quads((None, None, None)):
        if stmt[0] not in ctxs and stmt[1] not in ignorePredicates:
            out.addN([stmt])
    return out

def graphEqual(a, b, ignorePredicates=[]):
    """
    compare graphs, omitting any metadata statements about contexts
    (especially modification times) and also any statements using the
    given predicates
    """
    stmtsA = set(graphWithoutMetadata(a, ignorePredicates))
    stmtsB = set(graphWithoutMetadata(b, ignorePredicates))
    if stmtsA == stmtsB:
        return True
    
    if log.getEffectiveLevel() <= logging.INFO:
        lost = stmtsA - stmtsB
        if lost:
            log.info("lost statements:")
            for s in lost:
                log.info("  %s", s)
        new = stmtsB - stmtsA
        if new:
            log.info("new statements:")
            for s in new:
                log.info("  %s", s)
    return False
