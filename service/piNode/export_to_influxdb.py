import time, logging
from influxdb import InfluxDBClient
from rdflib import Namespace

log = logging.getLogger()
ROOM = Namespace('http://projects.bigasterisk.com/room/')

class InfluxExporter(object):
    def __init__(self, configGraph, influxHost='bang6'):
        self.graph = configGraph
        self.influx = InfluxDBClient(influxHost, 9060, 'root', 'root', 'main')
        self.lastExport = 0
        self.lastSent = {}  # (subj, measurementName, tags) : (time, value)

        self.measurements = {} # (subj, predicate) : measurement
        for s, m in self.graph.subject_objects(ROOM['influxMeasurement']):
            self.measurements[(s, self.graph.value(m, ROOM['predicate']))] = m
        
    def exportToInflux(self, currentStatements):
        graph = self.graph
        now = int(time.time())
      
        log.debug('influxdb export:')

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
                    
                if not self.shouldSendNewPoint(now, stmt[0], measurementName,
                                               tags, value):
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
        if rdfValue == ROOM['motion']:
            value = 1
        elif rdfValue == ROOM['noMotion']:
            value = 0
        else:
            value = rdfValue.toPython()
            if not isinstance(value, (int, float)):
                raise NotImplementedError('value=%r' % value)
        return value
            
    def shouldSendNewPoint(self, now, subj, measurementName, tags, value):
        key = (subj, measurementName, tuple(sorted(tags.items())))
        if key in self.lastSent:
            lastTime, lastValue = self.lastSent[key]
            if lastValue == value and lastTime > now - 3600:
                log.debug('skip influx point %r', key)
                return False

        self.lastSent[key] = (now, value)
        return True
