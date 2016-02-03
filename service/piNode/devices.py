from __future__ import division

import time, logging, os
from rdflib import Namespace, URIRef, Literal

try:
    import pigpio
except ImportError:
    pigpio = None
import w1thermsensor
    
import sys

log = logging.getLogger()
ROOM = Namespace('http://projects.bigasterisk.com/room/')
XSD = Namespace('http://www.w3.org/2001/XMLSchema#')
RDFS = Namespace('http://www.w3.org/2000/01/rdf-schema#')

class DeviceType(object):
    deviceType = NotImplementedError
    @classmethod
    def findInstances(cls, graph, board, pi):
        """
        return any number of instances of this class for all the separately
        controlled devices on the board. Two LEDS makes two instances,
        but two sensors on the same onewire bus makes only one device
        (which yields more statements).
        """
        log.debug("graph has any connected devices of type %s?", cls.deviceType)
        for row in graph.query("""SELECT ?dev ?gpioNumber WHERE {
                                    ?board :hasPin ?pin .
                                    ?pin :gpioNumber ?gpioNumber;
                                         :connectedTo ?dev .
                                    ?dev a ?thisType .
                                  } ORDER BY ?dev""",
                               initBindings=dict(board=board,
                                                 thisType=cls.deviceType)):
            yield cls(graph, row.dev, pi, int(row.gpioNumber))

    def __init__(self, graph, uri, pi, pinNumber):
        self.graph, self.uri, self.pi = graph, uri, pi
        self.pinNumber = pinNumber
        self.hostStateInit()

    def hostStateInit(self):
        """
        If you don't want to use __init__, you can use this to set up
        whatever storage you might need for hostStatements
        """
        
    def description(self):
        return {
            'uri': self.uri,
            'className': self.__class__.__name__,
            'pinNumber': getattr(self, 'pinNumber', None),
            'outputPatterns': self.outputPatterns(),
            'watchPrefixes': self.watchPrefixes(),
            'outputWidgets': self.outputWidgets(),
        }

    def hostStatements(self):
        """
        Like readFromPoll but these statements come from the host-side
        python code, not the connected device. Include output state
        (e.g. light brightness) if its master version is in this
        object. This method is called on /graph requests so it should
        be fast.
        """
        return []
        
    def watchPrefixes(self):
        """
        subj,pred pairs of the statements that might be returned from
        readFromPoll, so the dashboard knows what it should
        watch. This should be eliminated, as the dashboard should just
        always watch the whole tree of statements starting self.uri
        """
        return []

    def poll(self):
        return [] # statements
    
    def outputPatterns(self):
        """
        Triple patterns, using None as a wildcard, that should be routed
        to sendOutput
        """
        return []

    def outputWidgets(self):
        """
        structs to make output widgets on the dashboard. ~1 of these per
        handler you have in sendOutput
        """
        return []
        
    def sendOutput(self, statements):
        """
        If we got statements that match this class's outputPatterns, this
        will be called with the statements that matched. 

        Todo: it would be fine to read back confirmations or
        whatever. Just need a way to collect them into graph statements.
        """
        raise NotImplementedError
        
_knownTypes = set()
def register(deviceType):
    _knownTypes.add(deviceType)
    return deviceType

@register
class MotionSensorInput(DeviceType):
    # compare motion sensor lib at http://pythonhosted.org/gpiozero/inputs/
    # which is a bit fancier
    deviceType = ROOM['MotionSensor']

    def setup(self):
        self.pi.set_mode(17, pigpio.INPUT)
        self.pi.set_pull_up_down(17, pigpio.PUD_DOWN)

    def poll(self):
        motion = self.pi.read(17)
        
        return [
            (self.uri, ROOM['sees'],
             ROOM['motion'] if motion else ROOM['noMotion']),
            self.recentMotionStatement(motion),
        ]

    def recentMotionStatement(self, motion):
        if not hasattr(self, 'lastMotionTime'):
            self.lastMotionTime = 0
        now = time.time()
        if motion:
            self.lastMotionTime = now
        recentMotion = now - self.lastMotionTime < 60 * 10
        return (self.uri, ROOM['seesRecently'],
                ROOM['motion'] if recentMotion else ROOM['noMotion'])        
    
    def watchPrefixes(self):
        return [
            (self.uri, ROOM['sees']),
            (self.uri, ROOM['seesRecently']),
        ]


@register
class RgbStrip(DeviceType):
    """3 PWMs for r/g/b on a strip"""
    # pigpio daemon is working fine, but
    # https://github.com/RPi-Distro/python-gpiozero/blob/59ba7154c5918745ac894ea03503667d6473c760/gpiozero/output_devices.py#L213
    # can also apparently do PWM
    deviceType = ROOM['RgbStrip']
    
    @classmethod
    def findInstances(cls, graph, board, pi):
        for row in graph.query("""SELECT DISTINCT ?dev ?r ?g ?b  WHERE {
                                    ?board
                                      :hasPin ?rpin;
                                      :hasPin ?gpin;
                                      :hasPin ?bpin .
                                    ?dev a :RgbStrip;
                                      :redChannel   ?rpin;
                                      :greenChannel ?gpin;
                                      :blueChannel  ?bpin .
                                    ?rpin :gpioNumber ?r .
                                    ?gpin :gpioNumber ?g .
                                    ?bpin :gpioNumber ?b .
                                  } ORDER BY ?dev""",
                               initBindings=dict(board=board),
                               initNs={'': ROOM}):
            log.debug('found rgb %r', row)
            yield cls(graph, row.dev, pi, row.r, row.g, row.b)

    def __init__(self, graph, uri, pi, r, g, b):
        self.graph, self.uri, self.pi = graph, uri, pi
        self.rgb = map(int, [r, g, b])
        self.value = '#000000'
            
    def setup(self):
        for i in self.rgb:
            self.pi.set_mode(i, pigpio.OUTPUT)
            self.pi.set_PWM_frequency(i, 200)
            self.pi.set_PWM_dutycycle(i, 0)
            
    def hostStatements(self):
        return [(self.uri, ROOM['color'], Literal(self.value))]
        
    def outputPatterns(self):
        return [(self.uri, ROOM['color'], None)]

    def _rgbFromHex(self, h):
        rrggbb = h.lstrip('#')
        return [int(x, 16) for x in [rrggbb[0:2], rrggbb[2:4], rrggbb[4:6]]]
    
    def sendOutput(self, statements):
        assert len(statements) == 1
        assert statements[0][:2] == (self.uri, ROOM['color'])

        rgb = self._rgbFromHex(statements[0][2])
        self.value = statements[0][2]

        for (i, v) in zip(self.rgb, rgb):
            self.pi.set_PWM_dutycycle(i, v)
        
    def outputWidgets(self):
        return [{
            'element': 'output-rgb',
            'subj': self.uri,
            'pred': ROOM['color'],
        }]


@register
class TempHumidSensor(DeviceType):
    deviceType = ROOM['TempHumidSensor']

    def __init__(self, *a, **kw):
        DeviceType.__init__(self, *a, **kw)
        sys.path.append('/opt/pigpio/EXAMPLES/Python/DHT22_AM2302_SENSOR')
        import DHT22
        self.sensor = DHT22.sensor(self.pi, self.pinNumber)
    
    def poll(self):
        self.sensor.trigger()
        humid, tempC = self.sensor.humidity(), self.sensor.temperature()

        stmts = set()
        if humid is not None:
            stmts.add((self.uri, ROOM['humidity'], Literal(round(humid, 2))))
        else:
            stmts.add((self.uri, RDFS['comment'],
                       Literal('DHT read returned None')))
        if tempC is not None:
            stmts.add((self.uri, ROOM['temperatureF'],
                       # see round() note in arduinoNode/devices.py
                       Literal(round(tempC * 9 / 5 + 32, 2))))
        else:
            stmts.add((self.uri, RDFS['comment'],
                       Literal('DHT read returned None')))
        return stmts
        
    def watchPrefixes(self):
        return [
            (self.uri, ROOM['temperatureF']),
            (self.uri, ROOM['humidity']),
        ]

@register
class PushbuttonInput(DeviceType):
    """add a switch to ground; we'll turn on pullup"""
    deviceType = ROOM['Pushbutton']

    def __init__(self, *a, **kw):
        DeviceType.__init__(self, *a, **kw)
        log.debug("setup switch on %r", self.pinNumber)
        self.pi.set_mode(self.pinNumber, pigpio.INPUT)
        self.pi.set_pull_up_down(self.pinNumber, pigpio.PUD_UP)

    def poll(self):
        closed = not self.pi.read(self.pinNumber)
        
        return [
            (self.uri, ROOM['buttonState'],
             ROOM['pressed'] if closed else ROOM['notPressed']),
        ]
        
    def watchPrefixes(self):
        return [
            (self.uri, ROOM['buttonState']),
        ]
        
@register
class OneWire(DeviceType):
    """
    Also see /my/proj/ansible/roles/raspi_io_node/tasks/main.yml for
    some system config that contains the pin number that you want to
    use for onewire. The pin number in this config is currently ignored.
    """
    deviceType = ROOM['OneWire']
    # deliberately written like arduinoNode's one for an easier merge.
    def __init__(self,  *a, **kw):
        DeviceType.__init__(self, *a, **kw)
        log.info("scan for w1 devices")
        self._sensors = w1thermsensor.W1ThermSensor.get_available_sensors()
        for s in self._sensors:
            # Something looks different about these ids
            # ('000003a5a94c') vs the ones I get from arduino
            # ('2813bea50300003d'). Not sure if I'm parsing them
            # differently or what.
            s.uri = URIRef(os.path.join(self.uri, 'dev-%s' % s.id))
            log.info('  found temperature sensor %s' % s.uri)
        
    def poll(self):
        try:
            stmts = []
            for sensor in self._sensors:
                stmts.append((self.uri, ROOM['connectedTo'], sensor.uri))
                try:
                    tempF = sensor.get_temperature(sensor.DEGREES_F)
                    stmts.append((sensor.uri, ROOM['temperatureF'],
                                  # see round() note in arduinoNode/devices.py
                                  Literal(round(tempF, 2))))
                except w1thermsensor.core.SensorNotReadyError as e:
                    log.warning(e)

            return stmts
        except Exception as e:
            log.error(e)
            os.abort()
            
    def watchPrefixes(self):
        return [(s.uri, ROOM['temperatureF']) for s in self._sensors]

        
@register
class LedOutput(DeviceType):
    deviceType = ROOM['LedOutput']

    def hostStateInit(self):
        self.value = 0
    
    def setup(self):
        self.pi.set_mode(self.pinNumber, pigpio.OUTPUT)
        self.pi.set_PWM_frequency(self.pinNumber, 200)
        self.pi.set_PWM_dutycycle(self.pinNumber, 0)

    def outputPatterns(self):
        return [(self.uri, ROOM['brightness'], None)]
    
    def sendOutput(self, statements):
        assert len(statements) == 1
        assert statements[0][:2] == (self.uri, ROOM['brightness'])
        self.value = float(statements[0][2])
        v = int(self.value * 255)
        self.pi.set_PWM_dutycycle(self.pinNumber, v)

    def hostStatements(self):
        return [(self.uri, ROOM['brightness'], Literal(self.value))]       
        
    def outputWidgets(self):
        return [{
            'element': 'output-slider',
            'min': 0,
            'max': 1,
            'step': 1 / 255,
            'subj': self.uri,
            'pred': ROOM['brightness'],
        }]

        
@register
class OnboardTemperature(DeviceType):
    deviceType = ROOM['OnboardTemperature']
    pollPeriod = 10
    @classmethod
    def findInstances(cls, graph, board, pi):
        for row in graph.query('''SELECT DISTINCT ?uri WHERE {
          ?board :onboardDevice ?uri . 
          ?uri a :OnboardTemperature .
        }''', initBindings=dict(board=board)):
            yield cls(graph, row.uri, pi, pinNumber=None)
    
    def poll(self):
        milliC = open('/sys/class/thermal/thermal_zone0/temp').read().strip()
        c = float(milliC) / 1000.
        f = c * 1.8 + 32
        return [
            (self.uri, ROOM['temperatureF'], Literal(f, datatype=XSD['decimal'])),
            ]

    def watchPrefixes(self):
        # these uris will become dynamic! see note on watchPrefixes
        # about eliminating it.
        return [(self.uri, ROOM['temperatureF']),
                ]
        
def makeDevices(graph, board, pi):
    out = []
    for dt in sorted(_knownTypes, key=lambda cls: cls.__name__):
        out.extend(dt.findInstances(graph, board, pi))
    return out
        
