from __future__ import division
import sys, cyclone.web, json, datetime, time
import arrow
from twisted.internet import reactor, task
from dateutil.tz import tzlocal
import math
import cyclone.sse
from locator import Locator, Measurement

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

from db import Db

class Devices(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        devices = []
        startCount = datetime.datetime.now(tzlocal()) - datetime.timedelta(seconds=60*20)
        for addr in db.addrs(startCount):
            # limit to "addr_type": "Public"
            name = None
            if addr == "00:ea:23:23:c6:c4":
                name = 'apollo'
            if addr == "00:ea:23:21:e0:a4":
                name = 'white'
            if addr == "00:ea:23:24:f8:d4":
                name = 'green'
            row = db.latestDetail(addr)
            if 'Eddystone-URL' in row:
                name = row['Eddystone-URL']
            devices.append({
                'addr': addr,
                'name': name})
        devices.sort(key=lambda d: (d['name'] or 'zzz',
                                    d['addr']))
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({'devices': devices}))


class Poller(object):
    def __init__(self):
        self.listeners = []  # Points handlers

        self.lastPointTime = {} # addr : secs
        self.lastValues = {} # addr : {sensor: (secs, rssi)}
        task.LoopingCall(self.poll).start(2)
        
    def poll(self):
        addrs = set(l.addr for l in self.listeners if l.addr)
        seconds = 60 * 20
        now = datetime.datetime.now(tzlocal())
        startTime = (now - datetime.timedelta(seconds=seconds))
        startTimeSec = arrow.get(startTime).timestamp
        for addr in addrs:
            points = {} # from: [offsetSec, rssi]
            for row in db.recentRssi(startTime, addr):
                t = (row['time'] - startTime).total_seconds()
                points.setdefault(row['from'], []).append([
                    round(t, 2), row['rssi']])
                self.lastValues.setdefault(addr, {})[row['from']] = (
                    now, row['rssi'])

            for pts in points.values():
                smooth(pts)

            if not points:
                continue
                
            last = max(pts[-1][0] + startTimeSec for pts in points.values())
            if self.lastPointTime.get(addr, 0) == last:
                continue
            self.lastPointTime[addr] = last
            msg = json.dumps({
                'addr': addr,
                'startTime': startTimeSec,
                'points': [{'from': k, 'points': v}
                           for k,v in sorted(points.items())]})
            for lis in self.listeners:
                if lis.addr == addr:
                    lis.sendEvent(msg)

    def lastValue(self, addr, maxSensorAgeSec=30):
        """note: only considers actively polled addrs"""
        out = {} # from: rssi
        now = datetime.datetime.now(tzlocal())
        for sensor, (t, rssi) in self.lastValues.get(addr, {}).iteritems():
            print 'consider %s %s' % (t, now)
            if (now - t).total_seconds() < maxSensorAgeSec:
                out[sensor] = rssi
        return out
                    
def smooth(pts):
    # see https://filterpy.readthedocs.io/en/latest/kalman/UnscentedKalmanFilter.html
    for i in range(0, len(pts)):
        if i == 0:
            prevT, smoothX = pts[i]
        else:
            t, x = pts[i]
            if t - prevT < 30:
                smoothX = .8 * smoothX + .2 * x
            else:
                smoothX = x
            pts[i] = [t, round(smoothX, 1)]
            prevT = t

class Points(cyclone.sse.SSEHandler):
    def __init__(self, application, request, **kw):
        cyclone.sse.SSEHandler.__init__(self, application, request, **kw)
        if request.headers['accept'] != 'text/event-stream':
            raise ValueError('ignoring bogus request')
        self.addr = request.arguments.get('addr', [None])[0]
                
    def bind(self):
        if not self.addr:
            return
        poller.listeners.append(self)
    def unbind(self):
        if not self.addr:
            return
        poller.listeners.remove(self)

class LocatorEstimatesPoller(object):
    def __init__(self):
        self.listeners = []
        self.lastResult = {}
        self.locator = Locator()
        task.LoopingCall(self.poll).start(1)

    def poll(self):
        addrs = set(l.addr for l in self.listeners if l.addr)
        now = datetime.datetime.now(tzlocal())
        cutoff = (now - datetime.timedelta(seconds=60))
        
        for addr in addrs:
            d = {} # from: [(t, rssi)]
            for row in db.recentRssi(cutoff, addr):
                d.setdefault(row['from'], []).append((row['time'].timestamp, row['rssi']))

            for pts in d.values():
                pts.sort()
                smooth(pts)
            
            meas = Measurement(dict((k, v[-1][1]) for k, v in d.items()))
            nearest = [
                (dist, coord) for dist, coord in self.locator.nearestPoints(meas) if dist < 25
            ]
            if nearest:
                weightedCoord = self.locator.estimatePosition(nearest)
            else:
                weightedCoord = [-999, -999, -999]
            self.lastResult[addr] = {'nearest': nearest, 'weightedCoord': weightedCoord}
            
        for lis in self.listeners:
            lis.sendEvent(self.lastResult[addr])

class PositionEstimates(cyclone.sse.SSEHandler):
    def __init__(self, application, request, **kw):
        cyclone.sse.SSEHandler.__init__(self, application, request, **kw)
        if request.headers['accept'] != 'text/event-stream':
            raise ValueError('ignoring bogus request')
        self.addr = request.arguments.get('addr', [None])[0]
                
    def bind(self):
        if not self.addr:
            return
        locatorEstimatesPoller.listeners.append(self)
    def unbind(self):
        if not self.addr:
            return
        locatorEstimatesPoller.listeners.remove(self)

class Sensors(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        sensors = db.sensors()
        
        t1 = datetime.datetime.now(tzlocal()) - datetime.timedelta(seconds=60*10)
        out = []

        allRows = list(db.recentRssi(t1))
        allRows.sort(key=lambda r: r['time'], reverse=True)

        for sens in sensors:
            rssiHist = {} # level: count
            for row in allRows:
                if row['from'] == sens:
                    bucket = (row['rssi'] // 5) * 5
                    rssiHist[bucket] = rssiHist.get(bucket, 0) + 1

            out.append({
                'from': sens,
                'count': sum(rssiHist.values()),
                'hist': rssiHist,
            })
            
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({'sensors': out}))
        
class Save(PrettyErrorHandler, cyclone.web.RequestHandler):
    def post(self):
        lines = open('saved_points').readlines()
        lineNum = len(lines) + 1
        row = poller.lastValue('00:ea:23:21:e0:a4')
        with open('saved_points', 'a') as out:
            out.write('%s %r\n' % (lineNum, row))
        self.write('wrote line %s: %r' % (lineNum, row))

db = Db()

poller = Poller()
locatorEstimatesPoller = LocatorEstimatesPoller()

reactor.listenTCP(
    9113,
    cyclone.web.Application([
        (r"/(|.*\.(?:js|html|json))$", cyclone.web.StaticFileHandler, {
            "path": ".", "default_filename": "beaconmap.html"}),
        (r"/devices", Devices),
        (r'/points', Points),
        (r'/sensors', Sensors),
        (r'/save', Save),
        (r'/positionEstimates', PositionEstimates),
    ]))
log.info('serving on 9113')
reactor.run()
