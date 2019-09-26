import time, logging, math, os, sys, socket
from influxdb import InfluxDBClient
from rdflib import Namespace
from twisted.internet import task

log = logging.getLogger()
ROOM = Namespace('http://projects.bigasterisk.com/room/')

class RetentionPolicies(object):
    def __init__(self, influx):
        self.influx = influx
        self.createdPolicies = set() # days

    def getCreatedPolicy(self, days):
        name = 'ret_%d_day' % days
        if days not in self.createdPolicies:
            self.influx.create_retention_policy(name,
                                                duration='%dd' % days,
                                                replication='1')
            self.createdPolicies.add(days)
        return name

class InfluxExporter(object):
    def __init__(self, configGraph, influxHost='bang6'):
        self.graph = configGraph
        self.influx = InfluxDBClient(influxHost, 9060, 'root', 'root', 'main')
        self.retentionPolicies = RetentionPolicies(self.influx)
        self.lastSent = {}
        self.lastExport = 0

        self.measurements = {} # (subj, predicate) : measurement
        for s, m in self.graph.subject_objects(ROOM['influxMeasurement']):
            self.measurements[(s, self.graph.value(m, ROOM['predicate']))] = m

    def exportStats(self, stats, paths, period_secs=10, retain_days=7):
        # graphite version of this in scales/graphite.py
        base = ['stats', os.path.basename(sys.argv[0]).split('.py')[0]]
        tags  = {'host': socket.gethostname()}
        def send():
            now = int(time.time())
            points = []
            def getVal(path):
                x = stats
                comps = path.split('.')[1:]
                for comp in comps:
                    x2 = x
                    x = getattr(x, comp, None)
                    if x is None:
                        x = x2[comp]
                        if x is None:
                            print("no path %s" % path)
                            return
                if math.isnan(x):
                    return
                points.append({
                    'measurement': '.'.join(base + comps[:-1]),
                    "tags": tags,
                    "fields": {comps[-1]: x},
                    "time": now
                })
            for path in paths:
                getVal(path)
            if points:
                self.influx.write_points(
                    points, time_precision='s',
                    retention_policy=self.retentionPolicies.getCreatedPolicy(days=retain_days))
                if self.lastExport == 0:
                    log.info('writing stats to %r', points)
                self.lastExport = now
                #print('send %r' % points)

        task.LoopingCall(send).start(period_secs, now=False)

    def exportToInflux(self, currentStatements):
        """
        looks for

        ?subj ?p ?value;
         :influxMeasurement [
           :measurement ?name;
           :predicate ?p;
           :tag [:key ?k; :value ?v], ...
         ]

        """
        graph = self.graph
        now = int(time.time())

        points = []
        for stmt in currentStatements:
            if (stmt[0], stmt[1]) in self.measurements:
                meas = self.measurements[(stmt[0], stmt[1])]
                measurementName = graph.value(meas, ROOM['measurement'])
                tags = {}
                for t in graph.objects(meas, ROOM['tag']):
                    k = graph.value(t, ROOM['key']).toPython()
                    tags[k] = graph.value(t, ROOM['value']).toPython()

                value = self.influxValue(stmt[2])
                pale = 3600
                if graph.value(meas, ROOM['pointsAtLeastEvery'], default=None):
                    pale = graph.value(meas, ROOM['pointsAtLeastEvery']).toPython()

                if not self.shouldSendNewPoint(now, stmt[0], measurementName,
                                               tags, value, pointsAtLeastEvery=pale):
                    continue

                points.append({
                    'measurement': measurementName,
                    "tags": tags,
                    "fields": {"value": value},
                    "time": now
                })
                log.debug('send to influx %r', points[-1])
        if points:
            self.influx.write_points(points, time_precision='s')

    def influxValue(self, rdfValue):
        if rdfValue in [ROOM['motion'], ROOM['pressed']]:
            value = 1
        elif rdfValue in [ROOM['noMotion'], ROOM['notPressed']]:
            value = 0
        else:
            value = rdfValue.toPython()
            if not isinstance(value, (int, float)):
                raise NotImplementedError('value=%r' % value)
        return value

    def shouldSendNewPoint(self, now, subj, measurementName, tags, value, pointsAtLeastEvery):
        key = (subj, measurementName, tuple(sorted(tags.items())))
        if key in self.lastSent:
            lastTime, lastValue = self.lastSent[key]
            if lastValue == value and lastTime > now - pointsAtLeastEvery:
                log.debug('skip influx point %r', key)
                return False

        self.lastSent[key] = (now, value)
        return True
