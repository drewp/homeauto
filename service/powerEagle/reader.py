#!bin/python
import json, logging, time
import sys
sys.path.append("/my/proj/homeauto/lib")
from logsetup import log
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor
from cyclone.httpclient import fetch
from influxdb import InfluxDBClient

from private_config import deviceIp, cloudId, installId, macId, periodSec

auth = (cloudId + ':' + installId).encode('base64').strip()
influx = InfluxDBClient('bang', 9060, 'root', 'root', 'main')

class Poller(object):
    def __init__(self, carbon):
        self.carbon = carbon
        reactor.callLater(0, self.poll)

    @inlineCallbacks
    def poll(self):
        ret = None
        startTime = time.time()
        try:
            resp = yield fetch(
                'http://{deviceIp}/cgi-bin/cgi_manager'.format(deviceIp=deviceIp),
                method='POST',
                headers={'Authorization': ['Basic %s' % auth]},
                postdata='''<LocalCommand>
                              <Name>get_usage_data</Name>
                              <MacId>0x{macId}</MacId>
                            </LocalCommand>
                            <LocalCommand>
                              <Name>get_price_blocks</Name>
                              <MacId>0x{macId}</MacId>
                            </LocalCommand>'''.format(macId=macId))
            ret = json.loads(resp.body)
            if ret['demand_units'] != 'kW':
                raise ValueError
            if ret['summation_units'] != 'kWh':
                raise ValueError
            influx.write_points([
                dict(measurement='housePowerW',
                     fields=dict(value=float(ret['demand']) * 1000),
                     tags=dict(house='berkeley'),
                     time=int(startTime)),
                dict(measurement='housePowerSumDeliveredKwh',
                     fields=dict(value=float(ret['summation_delivered'])),
                     tags=dict(house='berkeley'),
                     time=int(startTime)),
                ], time_precision='s')
        except Exception as e:
            log.error("failed: %r", e)
            log.error(repr(ret))

        now = time.time()
        goal = startTime + periodSec - .2
        reactor.callLater(max(1, goal - now), self.poll)


log.setLevel(logging.INFO)
influx = InfluxDBClient('bang', 9060, 'root', 'root', 'main')

p = Poller(influx)
reactor.run()
