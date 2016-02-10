import time, logging
from rdflib import ConjunctiveGraph
from rdflib.parser import StringInputSource
import treq
from twisted.internet.defer import inlineCallbacks, returnValue
log = logging.getLogger('fetch')

from private_ipv6_addresses import ipv6Addresses

@inlineCallbacks
def addTrig(graph, url, timeout=2):
    t1 = time.time()
    # workaround for some reason my ipv6 names don't resolve
    for name, addr in ipv6Addresses.iteritems():
        url = url.replace('/' + name + ':', '/[' + addr + ']:')
    log.debug('    fetching %r', url)
    response = yield treq.get(url, headers={'accept': ['application/trig']}, timeout=timeout)
    if response.code != 200:
        raise ValueError("status %s from %s" % (response.code, url))
    g = ConjunctiveGraph()
    g.parse(StringInputSource((yield response.content())), format='trig')
    fetchTime = time.time() - t1
    log.debug('    %r done in %.04f sec', url, fetchTime)
    graph.addN(g.quads())
    returnValue(fetchTime)
