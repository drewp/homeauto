"""
We get output statements that are like light9's deviceAttrs (:dev1 :color "#ff0000"),
convert those to outputAttrs (:dev1 :red 255; :green 0; :blue 0) and post them to mqtt.

This is like light9/bin/collector.
"""
import json
from mqtt_client import MqttClient
from docopt import docopt
from rdflib import Namespace
from twisted.internet import reactor
import cyclone.web
from greplin import scales
from greplin.scales.cyclonehandler import StatsHandler

from standardservice.logsetup import log, verboseLogging
import rdf_over_http
from cycloneerr import PrettyErrorHandler

ROOM = Namespace('http://projects.bigasterisk.com/room/')

STATS = scales.collection('/root',
                          scales.PmfStat('putRequests'),
                          scales.PmfStat('statement'),
                          scales.PmfStat('mqttPublish'),
)

devs = {
    ROOM['kitchenLight']: {
        'root': 'h801_skylight',
    },
    ROOM['kitchenCounterLight']: {
        'root': 'h801_counter',
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
#-t theater_blaster/ir_out -m 'input_game'
#-t theater_blaster/ir_out -m 'input_bd'
#-t theater_blaster/ir_out -m 'input_cbl'
#-t theater_blaster/ir_out -m 'input_pc'
#-t theater_blaster/ir_out/volume_up -m '{"times":1}'
#-t theater_blaster/ir_out/volume_down -m '{"times":1}'
}


class OutputPage(PrettyErrorHandler, cyclone.web.RequestHandler):
    @STATS.putRequests.time()
    def put(self):
        for stmt in rdf_over_http.rdfStatementsFromRequest(
                self.request.arguments,
                self.request.body,
                self.request.headers):
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
                self._publish(topic=f'theater_blaster/ir_out/volume_{which}',
                              message=json.dumps({'timed': abs(delta)}))
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

    @STATS.mqttPublish.time()
    def _publish(self, topic: str, messageJson: object=None,
                 message: str=None):
        log.debug(f'mqtt.publish {topic} {message} {messageJson}')
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
        (r'/stats/(.*)', StatsHandler, {'serverName': 'rdf_to_mqtt'}),
        ], mqtt=mqtt, debug=arg['-v']), interface='::')
    log.warn('serving on %s', port)

    reactor.run()
