"""
Subscribe to mqtt topics; generate RDF statements.
"""
import glob
import json
import logging
import os

from rdfdb.patch import Patch

from mqtt_message import graphFromMessage
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence, Set, Tuple, Union, cast

import cyclone.sse
import cyclone.web
import export_to_influxdb
import prometheus_client
import rx
import rx.operators
import rx.scheduler.eventloop
from docopt import docopt
from export_to_influxdb import InfluxExporter
from mqtt_client import MqttClient
from patchablegraph import (CycloneGraphEventsHandler, CycloneGraphHandler, PatchableGraph)
from prometheus_client import Counter, Gauge, Histogram, Summary
from prometheus_client.exposition import generate_latest
from prometheus_client.registry import REGISTRY
from rdfdb.rdflibpatch import graphFromQuads
from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef
from rdflib.graph import ConjunctiveGraph
from rdflib.term import Node
from rx.core import Observable
from rx.core.typing import Mapper
from standardservice.logsetup import log, verboseLogging
from twisted.internet import reactor, task
from inference import Inference
from button_events import button_events
from patch_cyclone_sse import patchCycloneSse

ROOM = Namespace('http://projects.bigasterisk.com/room/')
MESSAGES_SEEN = Counter('mqtt_messages_seen', '')
collectors = {}

patchCycloneSse()


def logGraph(debug: Callable, label: str, graph: Graph):
    n3 = cast(bytes, graph.serialize(format="n3"))
    debug(label + ':\n' + n3.decode('utf8'))


def appendLimit(lst, elem, n=10):
    del lst[:len(lst) - n + 1]
    lst.append(elem)


def parseDurationLiteral(lit: Literal) -> float:
    if lit.endswith('s'):
        return float(lit.split('s')[0])
    raise NotImplementedError(f'duration literal: {lit}')


@dataclass
class StreamPipelineStep:
    uri: URIRef  # a :MqttStatementSource
    config: Graph

    def makeOutputStream(self, inStream: Observable) -> Observable:
        return inStream


class Filters(StreamPipelineStep):

    def makeOutputStream(self, inStream: Observable) -> Observable:
        jsonEq = self.config.value(self.uri, ROOM['filterPayloadJsonEquals'])
        if jsonEq:
            required = json.loads(jsonEq.toPython())

            def eq(jsonBytes):
                msg = json.loads(jsonBytes.decode('utf8'))
                return msg == required

            outStream = rx.operators.filter(eq)(inStream)
        else:
            outStream = inStream
        return outStream


class Parser(StreamPipelineStep):

    def makeOutputStream(self, inStream: Observable) -> Observable:
        parser = self.getParser()
        return parser(inStream)

    def getParser(self) -> Callable[[Observable], Observable]:
        parserType = cast(URIRef, self.config.value(self.uri, ROOM['parser']))
        func = self.getParserFunc(parserType)
        return rx.operators.map(cast(Mapper, func))

    def getParserFunc(self, parserType: URIRef) -> Callable[[bytes], Node]:
        if parserType == XSD.double:
            return lambda v: Literal(float(v))
        elif parserType == ROOM['tagIdToUri']:
            return self.tagIdToUri
        elif parserType == ROOM['onOffBrightness']:
            return lambda v: Literal(0.0 if v == b'OFF' else 1.0)
        elif parserType == ROOM['jsonBrightness']:
            return self.parseJsonBrightness
        elif ROOM['ValueMap'] in self.config.objects(parserType, RDF.type):
            return lambda v: self.remap(parserType, v.decode('utf8'))
        elif parserType == ROOM['rfCode']:
            return self.parseJsonRfCode
        elif parserType == ROOM['tradfri']:
            return self.parseTradfriMessage
        else:
            raise NotImplementedError(parserType)

    def tagIdToUri(self, value: bytes) -> URIRef:
        justHex = value.decode('utf8').replace('-', '').lower()
        int(justHex, 16)  # validate
        return URIRef(f'http://bigasterisk.com/rfidCard/{justHex}')

    def parseJsonBrightness(self, mqttValue: bytes):
        msg = json.loads(mqttValue.decode('utf8'))
        return Literal(float(msg['brightness'] / 255) if msg['state'] == 'ON' else 0.0)

    def remap(self, parser, valueStr: str) -> Node:
        g = self.config
        value = Literal(valueStr)
        for entry in g.objects(parser, ROOM['map']):
            if value == g.value(entry, ROOM['from']):
                to_ = g.value(entry, ROOM['to'])
                if not isinstance(to_, Node):
                    raise TypeError(f'{to_=}')
                return to_
        raise KeyError(value)

    def parseJsonRfCode(self, mqttValue: bytes):
        msg = json.loads(mqttValue.decode('utf8'))
        return Literal('%08x%08x' % (msg['code0'], msg['code1']))

    def parseTradfriMessage(self, mqttValue: bytes) -> Node:
        log.info(f'trad {mqttValue}')
        return Literal('todo')


class Converters(StreamPipelineStep):

    def makeOutputStream(self, inStream: Observable) -> Observable:
        out = inStream
        g = self.config
        for conv in g.items(g.value(self.uri, ROOM['conversions'])):
            out = self.conversionStep(conv)(out)
        return out

    def conversionStep(self, conv: Node) -> Callable[[Observable], Observable]:
        g = self.config
        if conv == ROOM['celsiusToFarenheit']:

            return rx.operators.map(cast(Mapper, self.c2f))
        elif g.value(conv, ROOM['ignoreValueBelow'], default=None) is not None:
            threshold = cast(Literal, g.value(conv, ROOM['ignoreValueBelow'])).toPython()
            return rx.operators.filter(lambda value: cast(Literal, value).toPython() >= threshold)
        elif conv == ROOM['buttonPress']:
            loop = rx.scheduler.eventloop.TwistedScheduler(reactor)
            return button_events(min_hold_sec=1.0, release_after_sec=1.0, scheduler=loop)
        else:
            raise NotImplementedError(conv)

    def c2f(self, value: Literal) -> Node:
        return Literal(round(cast(float, value.toPython()) * 1.8 + 32, 2))


class Rdfizer(StreamPipelineStep):

    def makeOutputStream(self, inStream: Observable) -> Observable:
        plans = list(self.config.objects(self.uri, ROOM['graphStatements']))
        log.debug(f'{self.uri=} has {len(plans)=}')
        if not plans:
            return rx.empty()
        outputQuadsSets = rx.combine_latest(*[self.makeQuads(inStream, plan) for plan in plans])
        return outputQuadsSets

    def makeQuads(self, inStream: Observable, plan: URIRef) -> Observable:

        def quadsFromValue(valueNode):
            return set([(self.uri, self.config.value(plan, ROOM['outputPredicate']), valueNode, self.uri)])

        def emptyQuads(element) -> Set[Tuple]:
            return set([])

        quads = rx.operators.map(cast(Mapper, quadsFromValue))(inStream)

        dur = self.config.value(plan, ROOM['statementLifetime'])
        if dur is not None:
            sec = parseDurationLiteral(dur)
            loop = rx.scheduler.eventloop.TwistedScheduler(reactor)
            quads = quads.pipe(
                rx.operators.debounce(sec, loop),
                rx.operators.map(cast(Mapper, emptyQuads)),
                rx.operators.merge(quads),
            )

        return quads


def truncTime():
    return round(time.time(), 3)


def tightN3(node: Union[URIRef, Literal]) -> str:
    return node.n3().replace('http://www.w3.org/2001/XMLSchema#', 'xsd:')


def serializeWithNs(graph: Graph, hidePrefixes=False) -> str:
    graph.bind('', ROOM)
    n3 = cast(bytes, graph.serialize(format='n3')).decode('utf8')
    if hidePrefixes:
        n3 = ''.join(line for line in n3.splitlines(keepends=True) if not line.strip().startswith('@prefix'))
    return n3


class EmptyTopicError(ValueError):
    pass


class MqttStatementSource:

    def __init__(self, uri: URIRef, config: Graph, masterGraph: PatchableGraph, mqtt, internalMqtt, debugPageData,
                 influxExport: InfluxExporter, inference: Inference):
        self.uri = uri
        self.config = config
        self.masterGraph = masterGraph
        self.debugPageData = debugPageData
        self.mqtt = mqtt  # deprecated
        self.internalMqtt = internalMqtt
        self.influxExport = influxExport
        self.inference = inference

        self.mqttTopic = self.topicFromConfig(self.config)
        if self.mqttTopic == b'':
            raise EmptyTopicError(f"empty topic for {uri=}")
        log.debug(f'new mqttTopic {self.mqttTopic}')

        self.debugSub = {
            'topic': self.mqttTopic.decode('ascii'),
            'recentMessageGraphs': [],
            'recentMetrics': [],
            'currentOutputGraph': {
                't': 1,
                'n3': "(n3)"
            },
        }
        self.debugPageData['subscribed'].append(self.debugSub)

        rawBytes: Observable = self.subscribeMqtt(self.mqttTopic)
        rawBytes.subscribe(on_next=self.countIncomingMessage)

        rawBytes.subscribe_(self.onMessage)

    def onMessage(self, raw: bytes):
        g = graphFromMessage(self.mqttTopic, raw)
        logGraph(log.debug, 'message graph', g)
        appendLimit(
            self.debugSub['recentMessageGraphs'],
            {  #
                't': truncTime(),
                'n3': serializeWithNs(g, hidePrefixes=True)
            })

        implied = self.inference.infer(g)
        self.updateMasterGraph(implied)

    def topicFromConfig(self, config) -> bytes:
        topicParts = list(config.items(config.value(self.uri, ROOM['mqttTopic'])))
        return b'/'.join(t.encode('ascii') for t in topicParts)

    def subscribeMqtt(self, topic: bytes):
        # goal is to get everyone on the internal broker and eliminate this
        mqtt = self.internalMqtt if topic.startswith(b'frontdoorlock') else self.mqtt
        return mqtt.subscribe(topic)

    def countIncomingMessage(self, msg: bytes):
        self.debugPageData['messagesSeen'] += 1
        MESSAGES_SEEN.inc()

    def updateInflux(self, newGraphs):
        for g in newGraphs:
            self.influxExport.exportToInflux(g)

    def updateMasterGraph(self, newGraph):
        log.debug(f'{self.uri} update to {len(newGraph)} statements')

        cg = ConjunctiveGraph()
        for stmt in newGraph:
            cg.add(stmt + (self.uri,))
            meas = stmt[0].split('/')[-1]
            if meas.startswith('airQuality'):
                where_prefix, type_ = meas[len('airQuality'):].split('door')
                where = where_prefix + 'door'
                metric = 'air'
                tags = {'loc': where.lower(), 'type': type_.lower()}
                val = stmt[2].toPython()
                if metric not in collectors:
                    collectors[metric] = Gauge(metric, 'measurement', labelnames=tags.keys())

                collectors[metric].labels(**tags).set(val)

        self.masterGraph.patchSubgraph(self.uri, cg)
        self.debugSub['currentOutputGraph']['n3'] = serializeWithNs(cg, hidePrefixes=True)


class Metrics(cyclone.web.RequestHandler):

    def get(self):
        self.add_header('content-type', 'text/plain')
        self.write(generate_latest(REGISTRY))


class DebugPageData(cyclone.sse.SSEHandler):

    def __init__(self, application, request):
        cyclone.sse.SSEHandler.__init__(self, application, request)
        self.lastSent = None

    def watch(self):
        try:
            dpd = self.settings.debugPageData
            js = json.dumps(dpd, sort_keys=True)
            if js != self.lastSent:
                log.debug('sending dpd update')
                self.sendEvent(message=js.encode('utf8'))
                self.lastSent = js
        except Exception:
            import traceback
            traceback.print_exc()

    def bind(self):
        self.loop = task.LoopingCall(self.watch)
        self.loop.start(1, now=True)

    def unbind(self):
        self.loop.stop()


if __name__ == '__main__':
    arg = docopt("""
    Usage: mqtt_to_rdf.py [options]

    -v        Verbose
    --cs=STR  Only process config filenames with this substring
    """)
    verboseLogging(arg['-v'])
    logging.getLogger('mqtt').setLevel(logging.INFO)
    logging.getLogger('mqtt_client').setLevel(logging.INFO)
    logging.getLogger('infer').setLevel(logging.INFO)
    log.info('log start')

    config = Graph()
    for fn in Path('.').glob('conf/*.n3'):
        if not arg['--cs'] or str(arg['--cs']) in str(fn):
            log.debug(f'loading {fn}')
            config.parse(str(fn), format='n3')
        else:
            log.debug(f'skipping {fn}')

    masterGraph = PatchableGraph()

    brokerHost = 'mosquitto-frontdoor.default.svc.cluster.local'
    brokerPort = 10210

    debugPageData = {
        # schema in index.ts
        'server': f'{brokerHost}:{brokerPort}',
        'messagesSeen': 0,
        'subscribed': [],
    }

    mqtt = MqttClient(clientId='mqtt_to_rdf', brokerHost='mosquitto-ext.default.svc.cluster.local', brokerPort=1883)  # deprecated
    internalMqtt = MqttClient(clientId='mqtt_to_rdf', brokerHost=brokerHost, brokerPort=brokerPort)

    influxExport = InfluxExporter(config, influxHost=os.environ['INFLUXDB_SERVICE_HOST'])

    inference = Inference()
    inference.setRules(config)
    expandedConfig = inference.infer(config)
    log.info('expanded config:')
    for stmt in sorted(expandedConfig):
        log.info(f'  {stmt}')
    srcs = []
    for src in sorted(expandedConfig.subjects(RDF.type, ROOM['MqttStatementSource'])):
        srcs.append(
            MqttStatementSource(src,
                                config,
                                masterGraph,
                                mqtt=mqtt,
                                internalMqtt=internalMqtt,
                                debugPageData=debugPageData,
                                influxExport=influxExport,
                                inference=inference))
    log.info(f'set up {len(srcs)} sources')

    peg = PatchableGraph()
    peg.patch(Patch(addQuads=[(s,p,o,URIRef('/config')) for s,p,o in expandedConfig]))

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
                          (r"/graph/config", CycloneGraphHandler, {
                              'masterGraph': peg,
                          }),
                          (r"/graph/mqtt", CycloneGraphHandler, {
                              'masterGraph': masterGraph
                          }),
                          (r"/graph/mqtt/events", CycloneGraphEventsHandler, {
                              'masterGraph': masterGraph
                          }),
                          (r'/debugPageData', DebugPageData),
                          (r'/metrics', Metrics),
                      ],
                                              mqtt=mqtt,
                                              internalMqtt=internalMqtt,
                                              masterGraph=masterGraph,
                                              debugPageData=debugPageData,
                                              debug=arg['-v']),
                      interface='::')
    log.info('serving on %s', port)

    reactor.run()
