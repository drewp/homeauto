from __future__ import division
import sys, cyclone.web, json, datetime, time
import arrow
from twisted.internet import reactor, task
from pymongo import MongoClient
from dateutil.tz import tzlocal
import math
import cyclone.sse
from locator import Locator, Measurement

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

class Devices(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        devices = []
        startCount = datetime.datetime.now(tzlocal()) - datetime.timedelta(seconds=60*60*2)
        filt = {
            #"addr_type": "Public",
        }
        for addr in scan.distinct('addr', filt):
            filtAddr = filt.copy()
            filtAddr['addr'] = addr
            row = scan.find_one(filtAddr, sort=[('t', -1)], limit=1)
            filtAddrRecent = filtAddr.copy()
            filtAddrRecent['t'] = {'$gt': startCount}
            freq = scan.count(filtAddrRecent)
            if not freq:
                continue
            name = None
            if addr == "00:ea:23:23:c6:c4":
                name = 'apollo'
            if addr == "00:ea:23:21:e0:a4":
                name = 'white'
            if addr == "00:ea:23:24:f8:d4":
                name = 'green'
            if 'Eddystone-URL' in row:
                name = row['Eddystone-URL']
            devices.append({
                'addr': addr,
                'recentCount': freq,
                'lastSeen': row['t'].isoformat(),
                'name': name})
        devices.sort(key=lambda d: (d['name'] or 'zzz',
                                    -d['recentCount'],
                                    d['addr']))
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({'devices': devices}))


class Poller(object):
    def __init__(self):
        self.listeners = []  # Points handlers

        self.lastPointTime = {} # addr : secs
        self.lastValues = {} # addr : {sensor: (secs, rssi)}
        task.LoopingCall(self.poll).start(1)
        
    def poll(self):
        addrs = set(l.addr for l in self.listeners if l.addr)
        seconds = 60 * 20
        now = datetime.datetime.now(tzlocal())
        startTime = (now - datetime.timedelta(seconds=seconds))
        startTimeSec = arrow.get(startTime).timestamp
        for addr in addrs:
            points = {} # from: [offsetSec, rssi]
            for row in scan.find({'addr': addr, 't': {'$gt': startTime},
                                  #'addr_type': 'Public',
                              },
                                 sort=[('t', 1)]):
                t = (arrow.get(row['t']) - startTime).total_seconds()
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
            for row in scan.find({'addr': addr, 't': {'$gt': cutoff}},
                                 sort=[('t', 1)]):
                d.setdefault(row['from'], []).append((arrow.get(row['t']).timestamp, row['rssi']))

            for pts in d.values():
                smooth(pts)
            meas = Measurement(dict((k, v[-1][1]) for k, v in d.items()))
            nearest = [
                (dist, coord) for dist, coord in self.locator.nearestPoints(meas) if dist < 25
            ]
            if nearest:
                floors = [row[1][2] for row in nearest]
                freqs = [(floors.count(z), z) for z in floors]
                freqs.sort()
                bestFloor = freqs[-1][1]
                sameFloorMatches = [(dist, coord) for dist, coord in nearest
                                    if coord[2] == bestFloor]
                weightedCoord = [0, 0, 0]
                totalWeight = 0
                for dist, coord in sameFloorMatches:
                    weight = 25 / (dist + .001)
                    totalWeight += weight
                    for i in range(3):
                        weightedCoord[i] += weight * coord[i]
                for i in range(3):
                    weightedCoord[i] /= totalWeight
            
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
        t1 = datetime.datetime.now(tzlocal()) - datetime.timedelta(seconds=60*10)
        out = []
        for sens in scan.distinct('from', {'t': {'$gt': t1}}):
            rssiHist = {} # level: count
            for row in scan.find({'from': sens, 't': {'$gt': t1}},
                                 {'_id': False, 'rssi': True}):
                bucket = (row['rssi'] // 5) * 5
                rssiHist[bucket] = rssiHist.get(bucket, 0) + 1

            recent = {}
            for row in scan.find({'from': sens},
                                 {'_id': False,
                                  'addr': True,
                                  't': True,
                                  'rssi': True,
                                  'addr_type': True},
                                 sort=[('t', -1)],
                                 modifiers={'$maxScan': 100000}):
                addr = row['addr']
                if addr not in recent:
                    recent[addr] = row
                    recent[addr]['t'] = arrow.get(recent[addr]['t']).timestamp

            out.append({
                'from': sens,
                'count': sum(rssiHist.values()),
                'hist': rssiHist,
                'recent': sorted(recent.values())
            })
            
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({'sensors': out}))


        
class Sensor(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        from_ = self.get_argument('from')
        if not from_:
            return
        seconds = int(self.get_argument('secs', default=60 * 2))
        startTime = (datetime.datetime.now(tzlocal()) -
                     datetime.timedelta(seconds=seconds))
        points = {} # addr : [offsetSec, rssi]
        for row in scan.find({'from': from_, 't': {'$gt': startTime},
                              #'addr_type': 'Public',
                          },
                             {'_id': False,
                              'addr': True,
                              't': True,
                              'rssi': True,
                          },
                             sort=[('t', 1)]):
            points.setdefault(row['addr'], []).append([
                round((arrow.get(row['t']) - startTime).total_seconds(), 2),
                row['rssi']])

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({
            'sensor': from_,
            'startTime': arrow.get(startTime).timestamp,
            'points': points}))

class Save(PrettyErrorHandler, cyclone.web.RequestHandler):
    def post(self):
        lines = open('saved_points').readlines()
        lineNum = len(lines) + 1
        row = poller.lastValue('00:ea:23:21:e0:a4')
        with open('saved_points', 'a') as out:
            out.write('%s %r\n' % (lineNum, row))
        self.write('wrote line %s: %r' % (lineNum, row))
        
scan = MongoClient('bang', 27017, tz_aware=True)['beacon']['scan']
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
        (r'/sensor', Sensor),
        (r'/save', Save),
        (r'/positionEstimates', PositionEstimates),
    ]))
log.info('serving on 9113')
reactor.run()
