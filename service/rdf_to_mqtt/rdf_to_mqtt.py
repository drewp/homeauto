"""
We get output statements that are like light9's deviceAttrs (:dev1 :color "#ff0000"),
convert those to outputAttrs (:dev1 :red 255; :green 0; :blue 0) and post them to mqtt.

This is like light9/bin/collector.
"""
import json
from mqtt_client import MqttClient
from docopt import docopt
from rdflib import Namespace, Literal
from twisted.internet import reactor
import cyclone.web

from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from standardservice.logsetup import log, verboseLogging
import rdf_over_http

ROOM = Namespace('http://projects.bigasterisk.com/room/')

devs = {
    ROOM['kitchenLight']: {
        'root': 'h801_skylight',
        'ctx': ROOM['kitchenH801']
    },
    ROOM['kitchenCounterLight']: {
        'root': 'h801_counter',
        'ctx': ROOM['kitchenH801']
    },
    ROOM['livingLampShelf']: {
        'root': 'sonoff_0/switch/sonoff_basic_relay/command',
        'ctx': ROOM['sonoff_0'],
        'values': 'binary',
    },
    ROOM['livingLamp1']: {
        'root': 'sonoff_1/switch/sonoff_basic_relay/command',
        'ctx': ROOM['sonoff_1'],
        'values': 'binary',
    },
    ROOM['livingLamp2']: {
        'root': 'sonoff_2/switch/sonoff_basic_relay/command',
        'ctx': ROOM['sonoff_2'],
        'values': 'binary',
    },
    ROOM['livingLamp3']: {
        'root': 'sonoff_3/switch/sonoff_basic_relay/command',
        'ctx': ROOM['sonoff_3'],
        'values': 'binary',
    },
    ROOM['livingLamp4']: {
        'root': 'sonoff_4/switch/sonoff_basic_relay/command',
        'ctx': ROOM['sonoff_4'],
        'values': 'binary',
    },
    ROOM['livingLamp5']: {
        'root': 'sonoff_5/switch/sonoff_basic_relay/command',
        'ctx': ROOM['sonoff_5'],
        'values': 'binary',
    },
#-t theater_blaster/ir_out -m 'input_game'
#-t theater_blaster/ir_out -m 'input_bd'
#-t theater_blaster/ir_out -m 'input_cbl'
#-t theater_blaster/ir_out -m 'input_pc'
#-t theater_blaster/ir_out/volume_up -m '{"times":1}'
#-t theater_blaster/ir_out/volume_down -m '{"times":1}'
}


class OutputPage(cyclone.web.RequestHandler):
    def put(self):
        for stmt in rdf_over_http.rdfStatementsFromRequest(
                self.request.arguments,
                self.request.body,
                self.request.headers):
            self._onStatement(stmt)

    def _onStatement(self, stmt):
        log.info(f'incoming statement: {stmt}')
        ignored = True
        for dev, attrs in devs.items():
            if stmt[0] == ROOM['frontWindow']:
                ignored = ignored and self._publishFrontScreenText(stmt)

            if stmt[0:2] == (dev, ROOM['brightness']):
                log.info(f'brightness request: {stmt}')
                brightness = stmt[2].toPython()

                if attrs.get('values', '') == 'binary':
                    self._publishOnOff(attrs, brightness)
                else:
                    self._publishRgbw(attrs, brightness)
                    # try to stop saving this; let the device be the master usually
                    self.settings.masterGraph.patchObject(
                        attrs['ctx'],
                        stmt[0], stmt[1], stmt[2])
                ignored = False
        if ignored:
            log.warn("ignoring %s", stmt)

    def _publishOnOff(self, attrs, brightness):
        msg = 'OFF'
        if brightness > 0:
            msg = 'ON'
        self._publish(topic=attrs['root'], message=msg)

    def _publishRgbw(self, attrs, brightness):
        for chan, scale in [('w1', 1),
                            ('r', 1),
                            ('g', .8),
                            ('b', .8)]:
            self._publish(
                topic=f"{attrs['root']}/light/kit_{chan}/command",
                messageJson={
                    'state': 'ON',
                    'brightness': int(brightness * 255)
                })

    def _publishFrontScreenText(self, stmt):
        ignored = True
        for line in ['line1', 'line2', 'line3', 'line4']:
            if stmt[1] == ROOM[line]:
                ignored = False
                self.settings.mqtt.publish(
                    b'frontwindow/%s' % line.encode('ascii'),
                    stmt[2].toPython())
        return ignored

    def _publish(self, topic: str, messageJson: object=None,
                 message: str=None):
        if messageJson is not None:
            message = json.dumps(messageJson)
        self.settings.mqtt.publish(
            topic.encode('ascii'),
            message.encode('ascii'))


if __name__ == '__main__':
    arg = docopt("""
    Usage: rdf_to_mqtt.py [options]

    -v   Verbose
    """)
    verboseLogging(arg['-v'])

    mqtt = MqttClient(clientId='rdf_to_mqtt', brokerPort=1883)

    port = 10008
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler,
         {"path": ".", "default_filename": "index.html"}),
        (r'/output', OutputPage),
        ], mqtt=mqtt, debug=arg['-v']), interface='::')
    log.warn('serving on %s', port)

    for dev, attrs in devs.items():
        masterGraph.patchObject(attrs['ctx'],
                                dev, ROOM['brightness'], Literal(0.0))

    reactor.run()
