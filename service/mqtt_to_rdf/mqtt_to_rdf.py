"""
Subscribe to mqtt topics; generate RDF statements.
"""
import json
from pathlib import Path
from typing import Callable, cast

import cyclone.web
from docopt import docopt
from mqtt_client import MqttClient
from patchablegraph import (
    CycloneGraphEventsHandler,
    CycloneGraphHandler,
    PatchableGraph,
)
from rdfdb.rdflibpatch import graphFromQuads
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD
from rdflib.term import Node
import rx
from rx.core import Observable
import rx.operators
import rx.scheduler.eventloop
from standardservice.logsetup import log, verboseLogging
from twisted.internet import reactor
import prometheus_client
from prometheus_client import Counter, Gauge, Histogram
from prometheus_client import Summary
from prometheus_client.exposition import generate_latest
from prometheus_client.registry import REGISTRY

from button_events import button_events

ROOM = Namespace('http://projects.bigasterisk.com/room/')


collectors = {}

def parseDurationLiteral(lit: Literal) -> float:
    if lit.endswith('s'):
        return float(lit.split('s')[0])
    raise NotImplementedError(f'duration literal: {lit}')


class MqttStatementSource:

    def __init__(self, uri: URIRef, config: Graph, masterGraph: PatchableGraph, mqtt, internalMqtt):
        self.uri = uri
        self.config = config
        self.masterGraph = masterGraph
        self.mqtt = mqtt  # deprecated
        self.internalMqtt = internalMqtt

        self.mqttTopic = self.topicFromConfig(self.config)
        log.debug(f'new mqttTopic {self.mqttTopic}')

        statPath = '/subscribed_topic/' + self.mqttTopic.decode('ascii').replace('/', '|')
        #scales.init(self, statPath)
        #self._mqttStats = scales.collection(statPath + '/incoming', scales.IntStat('count'), scales.RecentFpsStat('fps'))

        rawBytes = self.subscribeMqtt(self.mqttTopic)
        rawBytes = self.addFilters(rawBytes)
        rawBytes = rx.operators.do_action(self.countIncomingMessage)(rawBytes)
        parsed = self.getParser()(rawBytes)

        g = self.config
        for conv in g.items(g.value(self.uri, ROOM['conversions'])):
            parsed = self.conversionStep(conv)(parsed)

        outputQuadsSets = rx.combine_latest(
            *[self.makeQuads(parsed, plan) for plan in g.objects(self.uri, ROOM['graphStatements'])])

        outputQuadsSets.subscribe_(self.updateQuads)

    def addFilters(self, rawBytes):
        jsonEq = self.config.value(self.uri, ROOM['filterPayloadJsonEquals'])
        if jsonEq:
            required = json.loads(jsonEq.toPython())

            def eq(jsonBytes):
                msg = json.loads(jsonBytes.decode('ascii'))
                return msg == required

            rawBytes = rx.operators.filter(eq)(rawBytes)
        return rawBytes

    def topicFromConfig(self, config) -> bytes:
        topicParts = list(config.items(config.value(self.uri, ROOM['mqttTopic'])))
        return b'/'.join(t.encode('ascii') for t in topicParts)

    def subscribeMqtt(self, topic):
        # goal is to get everyone on the internal broker and eliminate this
        mqtt = self.internalMqtt if topic.startswith(b'frontdoorlock') else self.mqtt
        return mqtt.subscribe(topic)

    def countIncomingMessage(self, _):
        pass  #self._mqttStats.fps.mark()
        #self._mqttStats.count += 1

    def getParser(self):
        g = self.config

        parser = g.value(self.uri, ROOM['parser'])
        if parser == XSD.double:
            return rx.operators.map(lambda v: Literal(float(v.decode('ascii'))))
        elif parser == ROOM['tagIdToUri']:
            return rx.operators.map(self.tagIdToUri)
        elif parser == ROOM['onOffBrightness']:
            return rx.operators.map(lambda v: Literal(0.0 if v == b'OFF' else 1.0))
        elif parser == ROOM['jsonBrightness']:
            return rx.operators.map(self.parseJsonBrightness)
        elif ROOM['ValueMap'] in g.objects(parser, RDF.type):
            return rx.operators.map(lambda v: self.remap(parser, v.decode('ascii')))
        elif parser == ROOM['rfCode']:
            return rx.operators.map(self.parseJsonRfCode)
        else:
            raise NotImplementedError(parser)

    def parseJsonBrightness(self, mqttValue: bytes):
        msg = json.loads(mqttValue.decode('ascii'))
        return Literal(float(msg['brightness'] / 255) if msg['state'] == 'ON' else 0.0)

    def parseJsonRfCode(self, mqttValue: bytes):
        msg = json.loads(mqttValue.decode('ascii'))
        return Literal('%08x%08x' % (msg['code0'], msg['code1']))

    def conversionStep(self, conv: Node) -> Callable[[Observable], Observable]:
        g = self.config
        if conv == ROOM['celsiusToFarenheit']:

            def c2f(value: Literal) -> Node:
                return Literal(round(cast(float, value.toPython()) * 1.8 + 32, 2))

            return rx.operators.map(c2f)
        elif g.value(conv, ROOM['ignoreValueBelow'], default=None) is not None:
            threshold = g.value(conv, ROOM['ignoreValueBelow'])
            return rx.operators.filter(lambda value: value.toPython() >= threshold.toPython())
        elif conv == ROOM['buttonPress']:
            loop = rx.scheduler.eventloop.TwistedScheduler(reactor)
            return button_events(min_hold_sec=1.0, release_after_sec=1.0, scheduler=loop)
        else:
            raise NotImplementedError(conv)

    def makeQuads(self, parsed, plan):
        g = self.config

        def quadsFromValue(valueNode):
            return set([(self.uri, g.value(plan, ROOM['outputPredicate']), valueNode, self.uri)])

        def emptyQuads(element):
            return set([])

        quads = rx.operators.map(quadsFromValue)(parsed)

        dur = g.value(plan, ROOM['statementLifetime'])
        if dur is not None:
            sec = parseDurationLiteral(dur)
            loop = rx.scheduler.eventloop.TwistedScheduler(reactor)
            quads = quads.pipe(
                rx.operators.debounce(sec, loop),
                rx.operators.map(emptyQuads),
                rx.operators.merge(quads),
            )

        return quads

    def updateQuads(self, newGraphs):
        newQuads = set.union(*newGraphs)
        g = graphFromQuads(newQuads)
        log.debug(f'{self.uri} update to {len(newQuads)} statements')

        for quad in newQuads:
            meas = quad[0].split('/')[-1]
            if meas.startswith('airQuality'):
                where_prefix, type_ = meas[len('airQuality'):].split('door')
                where = where_prefix + 'door'
                metric = 'air'
                tags = {'loc': where.lower(), 'type': type_.lower()}
                val = quad[2].toPython()
                if metric not in collectors:
                    collectors[metric] = Gauge(metric, 'measurement', labelnames=tags.keys())

                collectors[metric].labels(**tags).set(val)

        self.masterGraph.patchSubgraph(self.uri, g)

    def tagIdToUri(self, value: bytearray) -> URIRef:
        justHex = value.decode('ascii').replace('-', '').lower()
        int(justHex, 16)  # validate
        return URIRef(f'http://bigasterisk.com/rfidCard/{justHex}')

    def remap(self, parser, valueStr: str):
        g = self.config
        value = Literal(valueStr)
        for entry in g.objects(parser, ROOM['map']):
            if value == g.value(entry, ROOM['from']):
                return g.value(entry, ROOM['to'])
        raise KeyError(value)


class Metrics(cyclone.web.RequestHandler):

    def get(self):
        self.add_header('content-type', 'text/plain')
        self.write(generate_latest(REGISTRY))


if __name__ == '__main__':
    arg = docopt("""
    Usage: mqtt_to_rdf.py [options]

    -v        Verbose
    --cs=STR  Only process config filenames with this substring
    """)
    verboseLogging(arg['-v'])

    config = Graph()
    for fn in Path('.').glob('config_*.n3'):
        if not arg['--cs'] or str(arg['--cs']) in str(fn):
            log.debug(f'loading {fn}')
            config.parse(str(fn), format='n3')
        else:
            log.debug(f'skipping {fn}')

    masterGraph = PatchableGraph()

    mqtt = MqttClient(clientId='mqtt_to_rdf', brokerHost='mosquitto-ext.default.svc.cluster.local', brokerPort=1883)  # deprecated
    internalMqtt = MqttClient(clientId='mqtt_to_rdf',
                              brokerHost='mosquitto-frontdoor.default.svc.cluster.local',
                              brokerPort=10210)

    srcs = []
    for src in config.subjects(RDF.type, ROOM['MqttStatementSource']):
        srcs.append(MqttStatementSource(src, config, masterGraph, mqtt=mqtt, internalMqtt=internalMqtt))
    log.info(f'set up {len(srcs)} sources')

    port = 10018
    reactor.listenTCP(port,
                      cyclone.web.Application([
                          (r"/()", cyclone.web.StaticFileHandler, {
                              "path": ".",
                              "default_filename": "index.html"
                          }),
                          (r"/build/(bundle.js)", cyclone.web.StaticFileHandler, {
                              "path": "build"
                          }),
                          (r"/graph/mqtt", CycloneGraphHandler, {
                              'masterGraph': masterGraph
                          }),
                          (r"/graph/mqtt/events", CycloneGraphEventsHandler, {
                              'masterGraph': masterGraph
                          }),
                          (r'/metrics', Metrics),
                      ],
                                              mqtt=mqtt,
                                              internalMqtt=internalMqtt,
                                              masterGraph=masterGraph,
                                              debug=arg['-v']),
                      interface='::')
    log.warn('serving on %s', port)

    reactor.run()
