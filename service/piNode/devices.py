"""
https://github.com/juniorug/libsensorPy is a similar project
"""
from __future__ import division

import time, logging, os
from rdflib import Namespace, URIRef, Literal
from twisted.internet import reactor, threads
from twisted.internet.defer import inlineCallbacks, returnValue
from greplin import scales

from devices_shared import RgbPixelsAnimation

log = logging.getLogger()
ROOM = Namespace('http://projects.bigasterisk.com/room/')
XSD = Namespace('http://www.w3.org/2001/XMLSchema#')
RDFS = Namespace('http://www.w3.org/2000/01/rdf-schema#')

try:
    import pigpio
except ImportError:
    pigpio = None
try:
    import rpi_ws281x
except ImportError:
    rpi_ws281x = None

def setupPwm(pi, pinNumber, hz=8000):
    pi.set_mode(pinNumber, pigpio.OUTPUT)
    # see http://abyz.co.uk/rpi/pigpio/cif.html#gpioCfgClock
    # and http://abyz.co.uk/rpi/pigpio/cif.html#gpioSetPWMfrequency
    actual = pi.set_PWM_frequency(pinNumber, hz)
    if actual != hz:
        raise ValueError('pwm actual=%s' % actual)
    pi.set_PWM_dutycycle(pinNumber, 0)


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
        scales.init(self, self.__class__.__name__)
        self.stats = scales.collection(self.__class__.__name__,
                                       scales.PmfStat('poll'),
                                       scales.PmfStat('output'),
        )
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
    """
    Triggering all the time? Try 5V VCC, per https://electronics.stackexchange.com/a/416295

                    0          30s          60s         90s                    10min
                    |           |           |           |          ...          |
    Sensor input    ******** ** ******* ****
    :sees output    ........ .. ....... ....
    :seesRecently   .............................................................
    :seesRecently30 ....................................
    :motionStart    x        x  x       x
    :motionStart30  x           x
    """
    # compare motion sensor lib at
    # https://gpiozero.readthedocs.org/en/v1.2.0/api_input.html#motion-sensor-d-sun-pir
    # which is a bit fancier
    deviceType = ROOM['MotionSensor']

    def __init__(self, graph, uri, pi, pinNumber):
        super(MotionSensorInput, self).__init__(graph, uri, pi, pinNumber)
        self.pi.set_mode(pinNumber, pigpio.INPUT)
        self.pi.set_pull_up_down(pinNumber, pigpio.PUD_DOWN)

    def hostStateInit(self):
        self.lastRead = None
        self.lastMotionStart30 = 0
        self.lastMotionStart90 = 0

    def poll(self):
        motion = self.pi.read(self.pinNumber)
        now  = time.time()

        oneshot = []
        if self.lastRead is not None and motion != self.lastRead:
            oneshot = [(self.uri, ROOM['sees'], ROOM['motionStart'])]
            for v, t in [('lastMotionStart30', 30), ('lastMotionStart90', 90)]:
                if now - getattr(self, v) > t:
                    oneshot.append((self.uri, ROOM['sees'], ROOM['motionStart%s' % t]))
                    setattr(self, v, now)
        self.lastRead = motion

        return {'latest': [
            (self.uri, ROOM['sees'],
             ROOM['motion'] if motion else ROOM['noMotion']),
        ] + self.recentMotionStatements(now, motion),
        'oneshot': oneshot}

    def recentMotionStatements(self, now, motion):
        if not hasattr(self, 'lastMotionTime'):
            self.lastMotionTime = 0
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
    """
    AM2302/DHT22 pinout is vcc-data-nc-gnd. VCC to 3.3V. Add 10k pullup on data.
    """
    deviceType = ROOM['TempHumidSensor']
    pollPeriod = 5

    def __init__(self, *a, **kw):
        DeviceType.__init__(self, *a, **kw)
        import DHT22
        self.sens = DHT22.sensor(self.pi, self.pinNumber)
        self.recentLowTemp = (0, None) # time, temp
        self.recentPeriodSec = 30

    def poll(self):
        stmts = set()

        now = time.time()
        if self.recentLowTemp[0] < now - self.recentPeriodSec:
            self.recentLowTemp = (0, None)

        if self.sens.staleness() < self.pollPeriod * 2:
            humid, tempC = self.sens.humidity(), self.sens.temperature()
            if humid > -999:
                stmts.add((self.uri, ROOM['humidity'], Literal(round(humid, 2))))
            else:
                stmts.add((self.uri, RDFS['comment'], Literal('No recent humidity measurement')))
            if tempC > -999:
                # see round() note in arduinoNode/devices.py
                tempF = round(tempC * 9 / 5 + 32, 2)
                stmts.add((self.uri, ROOM['temperatureF'], Literal(tempF)))
                if self.recentLowTemp[1] is None or tempF < self.recentLowTemp[1]:
                    self.recentLowTemp = (now, tempF)
            else:
                stmts.add((self.uri, RDFS['comment'], Literal('No recent temperature measurement')))
        else:
            stmts.add((self.uri, RDFS['comment'],
                       Literal('No recent DHT response (%.02f sec old)' % self.sens.staleness())))

        if self.recentLowTemp[1] is not None:
            stmts.add((self.uri, ROOM['recentLowTemperatureF'], Literal(self.recentLowTemp[1])))

        self.sens.trigger()

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
    pollPeriod = 2
    # deliberately written like arduinoNode's one for an easier merge.
    def __init__(self,  *a, **kw):
        DeviceType.__init__(self, *a, **kw)
        import w1thermsensor
        log.info("scan for w1 devices")
        self.SensorNotReadyError = w1thermsensor.core.SensorNotReadyError
        self.ResetValueError = w1thermsensor.core.ResetValueError
        self._sensors = w1thermsensor.W1ThermSensor.get_available_sensors()
        for s in self._sensors:
            # Something looks different about these ids
            # ('000003a5a94c') vs the ones I get from arduino
            # ('2813bea50300003d'). Not sure if I'm parsing them
            # differently or what.
            s.uri = URIRef(os.path.join(self.uri, 'dev-%s' % s.id))
            log.info('  found temperature sensor %s' % s.uri)

    @inlineCallbacks
    def poll(self):
        try:
            stmts = []
            for sensor in self._sensors:
                stmts.append((self.uri, ROOM['connectedTo'], sensor.uri))
                try:
                    tempF = yield threads.deferToThread(sensor.get_temperature, sensor.DEGREES_F)
                    stmts.append((sensor.uri, ROOM['temperatureF'],
                                  # see round() note in arduinoNode/devices.py
                                  Literal(round(tempF, 2))))
                except (self.SensorNotReadyError, self.ResetValueError) as e:
                    log.warning(e)

            returnValue(stmts)
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
        if (self.uri, ROOM['fade'], None) in self.graph:
            # incomplete- the object could be fade settings
            self.fv = FilteredValue(self._setPwm)
        else:
            _setPwm = self._setPwm
            class Instant(object):
                def set(self, goal):
                    _setPwm(goal)
            self.fv = Instant()
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
        v = max(0, min(255, int((x ** self.gamma)* 255)))
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

pixelStats = scales.collection('/rgbPixels',
                               scales.PmfStat('updateOutput'),
                               scales.PmfStat('currentColors'),
                               scales.PmfStat('poll'),
                               )

@register
class RgbPixels(DeviceType):
    """chain of ws2812 rgb pixels on pin GPIO18"""
    deviceType = ROOM['RgbPixels']

    def hostStateInit(self):
        self.anim = RgbPixelsAnimation(self.graph, self.uri, self.updateOutput)
        log.debug('%s maxIndex = %s', self.uri, self.anim.maxIndex())
        self.neo = rpi_ws281x.Adafruit_NeoPixel(self.anim.maxIndex() + 1, pin=18)
        self.neo.begin()

        colorOrder, stripType = self.anim.getColorOrder(self.graph, self.uri)

    def sendOutput(self, statements):
        self.anim.onStatements(statements)

    @pixelStats.updateOutput.time()
    def updateOutput(self):
        if 0:
            for _, _, sg in self.anim.groups.values():
                print (sg.uri, sg.current)
            print (list(self.anim.currentColors()))
            return

        with pixelStats.currentColors.time():
            colors = self.anim.currentColors()

        for idx, (r, g, b) in colors:
            if idx < 4:
                log.debug('out color %s (%s,%s,%s)', idx, r, g, b)
            self.neo.setPixelColorRGB(idx, r, g, b)
        self.neo.show()

    @pixelStats.poll.time()
    def poll(self):
        self.anim.step()
        return []

    def hostStatements(self):
        return self.anim.hostStatements()

    def outputPatterns(self):
        return self.anim.outputPatterns()

    def outputWidgets(self):
        return self.anim.outputWidgets()

@register
class Lcd8544(DeviceType):
    """PCD8544 lcd (nokia 5110)"""
    deviceType = ROOM['RgbStrip']

    @classmethod
    def findInstances(cls, graph, board, pi):
        for row in graph.query("""
      SELECT DISTINCT ?dev ?din ?clk ?dc ?rst  WHERE {
        ?dev a :Lcd8544 .
        ?board :hasPin ?dinPin . ?dev :din ?dinPin . ?dinPin :gpioNumber ?din .
        ?board :hasPin ?clkPin . ?dev :clk ?clkPin . ?clkPin :gpioNumber ?clk .
        ?board :hasPin ?dcPin .  ?dev :dc ?dcPin .   ?dcPin :gpioNumber ?dc .
        ?board :hasPin ?rstPin . ?dev :rst ?rstPin . ?rstPin :gpioNumber ?rst .
      } ORDER BY ?dev""",
                               initBindings=dict(board=board),
                               initNs={'': ROOM}):
            log.debug('found lcd %r', row)
            yield cls(graph, row.dev, pi,
                      int(row.din), int(row.clk),
                      int(row.dc), int(row.rst))

    def __init__(self, graph, uri, pi, din, clk, dc, rst):
        super(Lcd8544, self).__init__(graph, uri, pi, None)


        import RPi.GPIO
        import Adafruit_Nokia_LCD
        import Adafruit_GPIO.SPI
        self.lcd = Adafruit_Nokia_LCD.PCD8544(
            dc=8, rst=7,
            spi=Adafruit_GPIO.SPI.BitBang(
                Adafruit_Nokia_LCD.GPIO.RPiGPIOAdapter(RPi.GPIO),
                sclk=clk,
                mosi=din))
        self.lcd.begin(contrast=60)

    def hostStatements(self):
        return []
        return [(self.uri, ROOM['color'], Literal(self.value))]

    def outputPatterns(self):
        return []
        return [(self.uri, ROOM['color'], None)]

    def sendOutput(self, statements):
        return
        assert len(statements) == 1
        assert statements[0][:2] == (self.uri, ROOM['color'])

        rgb = self._rgbFromHex(statements[0][2])
        self.value = statements[0][2]

        for (i, v) in zip(self.rgb, rgb):
            self.pi.set_PWM_dutycycle(i, v)

    def outputWidgets(self):
        return []
        return [{
            'element': 'output-rgb',
            'subj': self.uri,
            'pred': ROOM['color'],
        }]

@register
class PwmBoard(DeviceType):
    """
    need this in /boot/config.txt
      dtparam=i2c_arm=on
    check for devices with
      apt-get install -y i2c-tools
      sudo i2cdetect -y 1

    gpio8 = bcm2 = sda1
    gpio9 = bcm3 = scl1
    They're next to the 3v3 pin.
    """
    deviceType = ROOM['PwmBoard']
    @classmethod
    def findInstances(cls, graph, board, pi):
        for row in graph.query("""SELECT DISTINCT ?dev WHERE {
          ?board :hasI2cBus ?bus .
          ?bus :connectedTo ?dev .
          ?dev a :PwmBoard .
        }""", initBindings=dict(board=board), initNs={'': ROOM}):
            outs = {}
            for out in graph.query("""SELECT DISTINCT ?area ?chan WHERE {
               ?dev :output [:area ?area; :channel ?chan] .
            }""", initBindings=dict(dev=row.dev), initNs={'': ROOM}):
                outs[out.area] = out.chan.toPython()
            yield cls(graph, row.dev, pi, outs)

    def __init__(self, graph, dev, pi, outs):
        super(PwmBoard, self).__init__(graph, dev, pi, pinNumber=None)
        import PCA9685
        self.pwm = PCA9685.PWM(pi, bus=1, address=0x40)
        self.pwm.set_frequency(1200)
        self.outs = outs
        self.values = {uri: 0 for uri in self.outs.keys()} # uri: brightness

    def hostStatements(self):
        return [(uri, ROOM['brightness'], Literal(b))
                for uri, b in self.values.items()]

    def outputPatterns(self):
        return [(area, ROOM['brightness'], None) for area in self.outs]

    def sendOutput(self, statements):
        assert len(statements) == 1
        assert statements[0][1] == ROOM['brightness'];
        chan = self.outs[statements[0][0]]
        value = float(statements[0][2])
        self.values[statements[0][0]] = value
        self.pwm.set_duty_cycle(chan, value * 100)

    def outputWidgets(self):
        return [{
            'element': 'output-slider',
            'min': 0,
            'max': 1,
            'step': 1 / 255,
            'subj': area,
            'pred': ROOM['brightness'],
        } for area in self.outs]


def makeDevices(graph, board, pi):
    out = []
    for dt in sorted(_knownTypes, key=lambda cls: cls.__name__):
        out.extend(dt.findInstances(graph, board, pi))
    return out
