import binascii
import json
import time
import traceback
from typing import Dict

from cyclone.httpclient import fetch
import cyclone.web
from patchablegraph import (
    CycloneGraphEventsHandler,
    CycloneGraphHandler,
    PatchableGraph,
)
from prometheus_client import Counter, Gauge, Summary
from prometheus_client.exposition import generate_latest
from prometheus_client.registry import REGISTRY
from rdflib import Literal, Namespace
from standardservice.logsetup import log, verboseLogging
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from docopt import docopt
from private_config import cloudId, deviceIp, installId, macId, periodSec
ROOM = Namespace("http://projects.bigasterisk.com/room/")

authPlain = cloudId + ':' + installId
auth = binascii.b2a_base64(authPlain.encode('ascii')).strip(b'=\n')

POLL = Summary('poll', 'Time in HTTP poll requests')
POLL_SUCCESSES = Counter('poll_successes', 'poll success count')
POLL_ERRORS = Counter('poll_errors', 'poll error count')


class Poller(object):

    def __init__(self, out: Dict[str, Gauge], graph):
        self.out = out
        self.graph = graph
        reactor.callLater(0, self.poll)

    @POLL.time()
    @inlineCallbacks
    def poll(self):
        ret = None
        startTime = time.time()
        try:
            url = (f'http://{deviceIp}/cgi-bin/cgi_manager').encode('ascii')
            resp = yield fetch(url,
                               method=b'POST',
                               headers={b'Authorization': [b'Basic %s' % auth]},
                               postdata=(f'''<LocalCommand>
                              <Name>get_usage_data</Name>
                              <MacId>0x{macId}</MacId>
                            </LocalCommand>
                            <LocalCommand>
                              <Name>get_price_blocks</Name>
                              <MacId>0x{macId}</MacId>
                            </LocalCommand>''').encode('ascii'),
                               timeout=10)
            ret = json.loads(resp.body)
            log.debug(f"response body {ret}")
            if ret['demand_units'] != 'kW':
                raise ValueError
            if ret['summation_units'] != 'kWh':
                raise ValueError

            demandW = float(ret['demand']) * 1000
            self.out['w'].set(demandW)

            sd = float(ret['summation_delivered'])
            if sd > 0:  # Sometimes nan
                self.out['kwh'].set(sd)

            if 'price' in ret:
                self.out['price'].set(float(ret['price']))

            self.graph.patchObject(context=ROOM['powerEagle'],
                                   subject=ROOM['housePower'],
                                   predicate=ROOM['instantDemandWatts'],
                                   newObject=Literal(demandW))
            POLL_SUCCESSES.inc()
        except Exception as e:
            POLL_ERRORS.inc()
            traceback.print_exc()
            log.error("failed: %r", e)
            log.error(repr(ret))

        now = time.time()
        goal = startTime + periodSec - .2
        reactor.callLater(max(1, goal - now), self.poll)


class Metrics(cyclone.web.RequestHandler):

    def get(self):
        self.add_header('content-type', 'text/plain')
        self.write(generate_latest(REGISTRY))


if __name__ == '__main__':
    arg = docopt("""
    Usage: reader.py [options]

    -v           Verbose
    --port PORT  Serve on port [default: 10016].
    """)
    verboseLogging(arg['-v'])

    out = {
        'w': Gauge('house_power_w', 'house power demand'),
        'kwh': Gauge('house_power_kwh', 'house power sum delivered'),
        'price': Gauge('house_power_price', 'house power price'),
    }
    masterGraph = PatchableGraph()
    p = Poller(out, masterGraph)

    reactor.listenTCP(
        int(arg['--port']),
        cyclone.web.Application([
            (r'/metrics', Metrics),
            (r"/graph/power", CycloneGraphHandler, {
                'masterGraph': masterGraph
            }),
            (r"/graph/power/events", CycloneGraphEventsHandler, {
                'masterGraph': masterGraph
            }),
        ],))
    reactor.run()
