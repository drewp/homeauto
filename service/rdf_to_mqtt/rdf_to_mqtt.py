"""
We get output statements that are like light9's deviceAttrs (:dev1 :color "#ff0000"),
convert those to outputAttrs (:dev1 :red 255; :green 0; :blue 0) and post them to mqtt.

This is like light9/bin/collector.
"""
import json

import cyclone.web
from cycloneerr import PrettyErrorHandler
from docopt import docopt
from greplin import scales
from greplin.scales.cyclonehandler import StatsHandler
from mqtt_client import MqttClient
from rdflib import Namespace
from standardservice.logsetup import log, verboseLogging
from twisted.internet import reactor

import rdf_over_http

ROOM = Namespace('http://projects.bigasterisk.com/room/')

STATS = scales.collection(
    '/root',
    scales.PmfStat('putRequests'),
    scales.PmfStat('statement'),
    scales.PmfStat('mqttPublish'),
)

devs = {
    ROOM['kitchenLight']: {
        'root': 'h801_skylight',
        'hasWhite': True,
    },
    ROOM['kitchenCounterLight']: {
        'root': 'h801_counter',
        'hasWhite': True,
    },
    ROOM['livingLampShelf']: {
        'root': 'sonoff_0/switch/sonoff_basic_relay/command',
        'values': 'binary',
    },
    ROOM['livingLampMantleEntry']: {
        'root': 'sonoff_1/switch/sonoff_basic_relay/command',
        'values': 'binary',
    },
    ROOM['livingLampMantleChair']: {
        'root': 'sonoff_2/switch/sonoff_basic_relay/command',
        'values': 'binary',
    },
    ROOM['livingLampToyShelf']: {
        'root': 'sonoff_3/switch/sonoff_basic_relay/command',
        'values': 'binary',
    },
    ROOM['livingLampPiano']: {
        'root': 'sonoff_4/switch/sonoff_basic_relay/command',
        'values': 'binary',
    },
    ROOM['theater']: {
        'root': 'theater_blaster/ir_out',
        'values': 'theaterOutputs',
    },
    ROOM['bedHeadboard']: {
        'root': 'bed/light/headboard/command',
        'hasWhite': True,
    },
    # https://github.com/Koenkk/zigbee2mqtt.io/blob/new_api/docs/information/mqtt_topics_and_message_structure.md#general
    ROOM['frontRoom1']: {
        'root': 'zigbee2mqtt/frontRoom1/set',
        'hasBrightness': True,
        'defaults': {
            'transition': 0,
        }
    },
    ROOM['frontRoom2']: {
        'root': 'zigbee2mqtt/frontRoom2/set',
        'hasBrightness': True,
        'defaults': {
            'transition': 0,
        }
    },
    ROOM['asherCeiling']: {
        'root': 'zigbee2mqtt/asherCeiling/set',
        'hasBrightness': True,
        'defaults': {
            'transition': 0,
        }
    },
    ROOM['stairTop']: {
        'root': 'zigbee2mqtt/stairTop/set',
        'hasBrightness': True,
        'defaults': {
            'transition': 0,
        }
    },
    ROOM['noname1']: { 'root': 'zigbee2mqtt/0xf0d1b8000001ffc6/set', 'hasBrightness': True, 'defaults': { 'transition': 0, } },
    ROOM['noname2']: { 'root': 'zigbee2mqtt/0xf0d1b80000023583/set', 'hasBrightness': True, 'defaults': { 'transition': 0, } },
    ROOM['noname3']: { 'root': 'zigbee2mqtt/0xf0d1b80000023708/set', 'hasBrightness': True, 'defaults': { 'transition': 0, } },
    ROOM['noname4']: { 'root': 'zigbee2mqtt/0xf0d1b80000022adc/set', 'hasBrightness': True, 'defaults': { 'transition': 0, } },
}


class OutputPage(PrettyErrorHandler, cyclone.web.RequestHandler):

    @STATS.putRequests.time()
    def put(self):
        for stmt in rdf_over_http.rdfStatementsFromRequest(self.request.arguments, self.request.body, self.request.headers):
            self._onStatement(stmt)

    @STATS.statement.time()
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
                ignored = False
            if stmt[0:2] == (dev, ROOM['inputSelector']):
                choice = stmt[2].toPython().decode('utf8')
                self._publish(topic=attrs['root'], message=f'input_{choice}')
                ignored = False
            if stmt[0:2] == (dev, ROOM['volumeChange']):
                delta = int(stmt[2].toPython())
                which = 'up' if delta > 0 else 'down'
                self._publish(topic=f'theater_blaster/ir_out/volume_{which}', message=json.dumps({'timed': abs(delta)}))
                ignored = False
            if stmt[0:2] == (dev, ROOM['color']):
                h = stmt[2].toPython()
                msg = {}
                if h.endswith(b'K'):  # accept "0.7*2200K" (brightness 0.7)
                    # see https://www.zigbee2mqtt.io/information/mqtt_topics_and_message_structure.html#zigbee2mqttfriendly_nameset
                    bright, kelvin = map(float, h[:-1].split(b'*'))
                    msg['state'] = 'ON'                    
                    msg["color_temp"] = round(1000000 / kelvin, 2)
                    msg['brightness'] = int(bright * 255)  # 1..20 look about the same
                else:
                    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
                    msg = {
                        'state': 'ON' if r or g or b else 'OFF',
                        'color': {
                            'r': r,
                            'g': g,
                            'b': b
                        },
                    }

                    if attrs.get('hasWhite', False):
                        msg['white_value'] = max(r, g, b)
                msg.update(attrs.get('defaults', {}))
                self._publish(topic=attrs['root'], message=json.dumps(msg))
                ignored = False

        if ignored:
            log.warn("ignoring %s", stmt)

    def _publishOnOff(self, attrs, brightness):
        msg = 'OFF'
        if brightness > 0:
            msg = 'ON'
        self._publish(topic=attrs['root'], message=msg)

    def _publishRgbw(self, attrs, brightness):
        for chan, scale in [('w1', 1), ('r', 1), ('g', .8), ('b', .8)]:
            self._publish(topic=f"{attrs['root']}/light/kit_{chan}/command",
                          messageJson={
                              'state': 'ON',
                              'brightness': int(brightness * 255)
                          })

    def _publishFrontScreenText(self, stmt):
        ignored = True
        for line in ['line1', 'line2', 'line3', 'line4']:
            if stmt[1] == ROOM[line]:
                ignored = False
                self.settings.mqtt.publish(b'frontwindow/%s' % line.encode('ascii'), stmt[2].toPython())
        return ignored

    @STATS.mqttPublish.time()
    def _publish(self, topic: str, messageJson: object = None, message: str = None):
        log.debug(f'mqtt.publish {topic} {message} {messageJson}')
        if messageJson is not None:
            message = json.dumps(messageJson)
        self.settings.mqtt.publish(topic.encode('ascii'), message.encode('ascii'))


if __name__ == '__main__':
    arg = docopt("""
    Usage: rdf_to_mqtt.py [options]

    -v   Verbose
    """)
    verboseLogging(arg['-v'])

    mqtt = MqttClient(clientId='rdf_to_mqtt', brokerHost='mosquitto-ext.default.svc.cluster.local', brokerPort=1883)

    port = 10008
    reactor.listenTCP(port,
                      cyclone.web.Application([
                          (r"/()", cyclone.web.StaticFileHandler, {
                              "path": ".",
                              "default_filename": "index.html"
                          }),
                          (r'/output', OutputPage),
                          (r'/stats/(.*)', StatsHandler, {
                              'serverName': 'rdf_to_mqtt'
                          }),
                      ],
                                              mqtt=mqtt,
                                              debug=arg['-v']),
                      interface='::')
    log.warn('serving on %s', port)

    reactor.run()
