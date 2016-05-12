from __future__ import division

import time, logging, os
from rdflib import Namespace, URIRef, Literal
from twisted.internet import reactor

try:
    import pigpio
except ImportError:
    pigpio = None
import w1thermsensor
try:
    import neopixel
except ImportError:
    neopixel = None

def setupPwm(pi, pinNumber, hz=8000):
    pi.set_mode(pinNumber, pigpio.OUTPUT)
    # see http://abyz.co.uk/rpi/pigpio/cif.html#gpioCfgClock
    # and http://abyz.co.uk/rpi/pigpio/cif.html#gpioSetPWMfrequency
    actual = pi.set_PWM_frequency(pinNumber, hz)
    if actual != hz:
        raise ValueError('pwm actual=%s' % actual)
    pi.set_PWM_dutycycle(pinNumber, 0)

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

    def hostStateInit(self):
        self.lastRead = None

    def poll(self):
        motion = self.pi.read(17)
        
        oneshot = []
        if self.lastRead is not None and motion != self.lastRead:
            oneshot = [(self.uri, ROOM['sees'], ROOM['motionStart'])]
        self.lastRead = motion
        
        return {'latest': [
            (self.uri, ROOM['sees'],
             ROOM['motion'] if motion else ROOM['noMotion']),
        ] + self.recentMotionStatements(motion),
        'oneshot': oneshot}

    def recentMotionStatements(self, motion):
        if not hasattr(self, 'lastMotionTime'):
            self.lastMotionTime = 0
        now = time.time()
        if motion:
            self.lastMotionTime = now
        dt = now - self.lastMotionTime
        return [(self.uri, ROOM['seesRecently'],
                 ROOM['motion'] if (dt < 60 * 10) else ROOM['noMotion']),
                (self.uri, ROOM['seesRecently30'],
                 ROOM['motion'] if (dt < 30) else ROOM['noMotion'])]
    
    def watchPrefixes(self):
        return [
            (self.uri, ROOM['sees']),
            (self.uri, ROOM['seesRecently']),
            (self.uri, ROOM['seesRecently30']),
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
            setupPwm(self.pi, i)
            
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
        self.lastClosed = None
        self.invert = (self.uri, ROOM['style'],
                       ROOM['inverted']) in self.graph

    def poll(self):
        closed = not self.pi.read(self.pinNumber)
        if self.invert:
            closed = not closed

        if self.lastClosed is not None and closed != self.lastClosed:
            log.debug('%s changed to %s', self.uri, closed)
            oneshot = [
                (self.uri, ROOM['buttonState'],
                 ROOM['press'] if closed else ROOM['release']),
            ]
        else:
            oneshot = []
        self.lastClosed = closed
            
        return {'latest': [
            (self.uri, ROOM['buttonState'],
             ROOM['pressed'] if closed else ROOM['notPressed']),
        ],
                'oneshot':oneshot}
        
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

class FilteredValue(object):
    def __init__(self, setter,
                 slew=2.0, # step/sec max slew rate
                 accel=5, # step/sec^2 acceleration
    ):
        self.setter = setter
        self.slew, self.accel = slew, accel
        
        self.x = None
        self.dx = 0
        self.goal = self.x
        self.lastStep = 0

    def set(self, goal):
        self.goal = goal
        self.step()

    def step(self):
        now = time.time()
        dt = min(.1, now - self.lastStep)
        self.lastStep = now

        if self.x is None:
            self.x = self.goal

        if self.goal > self.x:
            self.dx = min(self.slew, self.dx + self.accel * dt)
        else:
            self.dx = max(-self.slew, self.dx - self.accel * dt)

        nextX = self.x + self.dx * dt
        if self.x == self.goal or (self.x < self.goal < nextX) or (self.x > self.goal > nextX):
            self.x = self.goal
            self.dx = 0
        else:
            self.x = nextX
            reactor.callLater(.05, self.step)

        #print "x= %(x)s dx= %(dx)s goal= %(goal)s" % self.__dict__
        self.setter(self.x)
        
@register
class LedOutput(DeviceType):
    deviceType = ROOM['LedOutput']

    def hostStateInit(self):
        self.value = 0
        self.fv = FilteredValue(self._setPwm)
        self.gamma = float(self.graph.value(self.uri, ROOM['gamma'], default=1))
    
    def setup(self):
        setupPwm(self.pi, self.pinNumber)

    def outputPatterns(self):
        return [(self.uri, ROOM['brightness'], None)]
    
    def sendOutput(self, statements):
        assert len(statements) == 1
        assert statements[0][:2] == (self.uri, ROOM['brightness'])
        self.value = float(statements[0][2])
        self.fv.set(self.value)

    def _setPwm(self, x):
        v = int((x ** self.gamma)* 255)
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
        log.debug('graph has any connected devices of type OnboardTemperature on %r?', board)
        for row in graph.query('''SELECT DISTINCT ?uri WHERE {
          ?board :onboardDevice ?uri . 
          ?uri a :OnboardTemperature .
        }''', initBindings=dict(board=board)):
            log.debug('  found %s', row.uri)
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

@register
class RgbPixels(DeviceType):
    """chain of ws2812 rgb pixels on pin GPIO18"""
    deviceType = ROOM['RgbPixels']

    def hostStateInit(self):
        px = self.graph.value(self.uri, ROOM['pixels'])
        self.pixelUris = list(self.graph.items(px))
        self.values = dict((uri, Literal('#000000')) for uri in self.pixelUris)
        colorOrder, stripType = self.getColorOrder(self.graph, self.uri)
        self.replace = {'ledArray': 'leds_%s' % self.pinNumber,
                        'ledCount': len(self.pixelUris),
                        'pin': self.pinNumber,
                        'ledType': 'WS2812',
                        'colorOrder': colorOrder
        }
        self.neo = neopixel.Adafruit_NeoPixel(len(self.values), pin=18, strip_type=stripType)
        self.neo.begin()

    def getColorOrder(self, graph, uri):
        colorOrder = graph.value(uri, ROOM['colorOrder'],
                                 default=ROOM['ledColorOrder/RGB'])
        head, tail = str(colorOrder).rsplit('/', 1)
        if head != str(ROOM['ledColorOrder']):
            raise NotImplementedError('%r colorOrder %r' % (uri, colorOrder))
        stripType = getattr(neopixel.ws, 'WS2811_STRIP_%s' % tail)
        return colorOrder, stripType
        
    def _rgbFromHex(self, h):
        rrggbb = h.lstrip('#')
        return [int(x, 16) for x in [rrggbb[0:2], rrggbb[2:4], rrggbb[4:6]]]
    
    def sendOutput(self, statements):
        px, pred, color = statements[0]
        if pred != ROOM['color']:
            raise ValueError(pred)
        rgb = self._rgbFromHex(color)
        if px not in self.values:
            raise ValueError(px)
        self.values[px] = Literal(color)
        self.neo.setPixelColorRGB(self.pixelUris.index(px), rgb[0], rgb[1], rgb[2])
        self.neo.show()

    def hostStatements(self):
        return [(uri, ROOM['color'], hexCol)
                for uri, hexCol in self.values.items()]
        
    def outputPatterns(self):
        return [(px, ROOM['color'], None) for px in self.pixelUris]

    def outputWidgets(self):
        return [{
            'element': 'output-rgb',
            'subj': px,
            'pred': ROOM['color'],
        } for px in self.pixelUris]

        
def makeDevices(graph, board, pi):
    out = []
    for dt in sorted(_knownTypes, key=lambda cls: cls.__name__):
        out.extend(dt.findInstances(graph, board, pi))
    return out
        
