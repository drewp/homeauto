#!bin/python
import json, time, os, binascii, traceback

from cyclone.httpclient import fetch
from docopt import docopt
from greplin import scales
from greplin.scales.cyclonehandler import StatsHandler
from influxdb import InfluxDBClient
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
import cyclone.web

from standardservice.logsetup import log, verboseLogging

from private_config import deviceIp, cloudId, installId, macId, periodSec

STATS = scales.collection('/root',
                          scales.PmfStat('poll'),
                          )

authPlain = cloudId + ':' + installId
auth = binascii.b2a_base64(authPlain.encode('ascii')).strip(b'=\n')

class Poller(object):
    def __init__(self, influx):
        self.influx = influx
        reactor.callLater(0, self.poll)

    @STATS.poll.time()
    @inlineCallbacks
    def poll(self):
        ret = None
        startTime = time.time()
        try:
            url = (f'http://{deviceIp}/cgi-bin/cgi_manager').encode('ascii')
            resp = yield fetch(
                url,
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
            log.debug(ret)
            if ret['demand_units'] != 'kW':
                raise ValueError
            if ret['summation_units'] != 'kWh':
                raise ValueError
            pts = [
                dict(measurement='housePowerW',
                     fields=dict(value=float(ret['demand']) * 1000),
                     tags=dict(house='berkeley'),
                     time=int(startTime))]
            sd = float(ret['summation_delivered'])
            if sd > 0: # Sometimes nan
                pts.append(dict(measurement='housePowerSumDeliveredKwh',
                                fields=dict(value=float()),
                                tags=dict(house='berkeley'),
                                time=int(startTime)))
            if 'price' in ret:
                pts.append(dict(
                    measurement='price',
                    fields=dict(price=float(ret['price']),
                                price_units=float(ret['price_units'])),
                    tags=dict(house='berkeley'),
                    time=int(startTime),
                ))

            self.influx.write_points(pts, time_precision='s')
        except Exception as e:
            traceback.print_exc()
            log.error("failed: %r", e)
            log.error(repr(ret))
            os.abort()

        now = time.time()
        goal = startTime + periodSec - .2
        reactor.callLater(max(1, goal - now), self.poll)


if __name__ == '__main__':
    arg = docopt("""
    Usage: reader.py [options]

    -v           Verbose
    --port PORT  Serve on port [default: 10016].
    """)
    verboseLogging(arg['-v'])

    influx = InfluxDBClient('bang', 9060, 'root', 'root', 'main')
    p = Poller(influx)

    reactor.listenTCP(
        int(arg['--port']),
        cyclone.web.Application(
            [
                (r'/stats/(.*)', StatsHandler, {'serverName': 'powerEagle'}),
                (r"/graph/power", CycloneGraphHandler, {'masterGraph': masterGraph}),
                (r"/graph/power/events", CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
            ],
        ))
    reactor.run()
