from __future__ import division

import itertools, logging, struct, os, sys
from rdflib import Namespace, RDF, URIRef, Literal
import time

from greplin import scales

from devices_shared import RgbPixelsAnimation

ROOM = Namespace('http://projects.bigasterisk.com/room/')
XSD = Namespace('http://www.w3.org/2001/XMLSchema#')
log = logging.getLogger()

def readLine(read):
    buf = ''
    for c in iter(lambda: read(1), '\n'):
        buf += c
    return buf

class DeviceType(object):
    deviceType = None
    @classmethod
    def findInstances(cls, graph, board):
        """
        return any number of instances of this class for all the separately
        controlled devices on the board. Two LEDS makes two instances,
        but two sensors on the same onewire bus makes only one device
        (which yields more statements).
        """
        for row in graph.query("""SELECT ?dev ?pinNumber WHERE {
                                    ?board :hasPin ?pin .
                                    ?pin :pinNumber ?pinNumber;
                                         :connectedTo ?dev .
                                    ?dev a ?thisType .
                                  } ORDER BY ?dev""",
                               initBindings=dict(board=board,
                                                 thisType=cls.deviceType),
                               initNs={'': ROOM}):
            log.info('found %s, a %s', row.dev, cls.deviceType)
            yield cls(graph, row.dev, int(row.pinNumber))

    # subclasses may add args to this
    def __init__(self, graph, uri, pinNumber):
        self.graph, self.uri = graph, uri
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

    def readFromPoll(self, read):
        """
        read an update message returned as part of a poll bundle. This may
        consume a varying number of bytes depending on the type of
        input (e.g. IR receiver).
        Returns rdf statements.
        """
        raise NotImplementedError('readFromPoll in %s' % self.__class__)

    def wantIdleOutput(self):
        return False

    def outputIdle(self, write):
        return

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

    def generateIncludes(self):
        """filenames of .h files to #include"""
        return []

    def generateArduinoLibs(self):
        """names of libraries for the ARDUINO_LIBS line in the makefile"""
        return []

    def generateGlobalCode(self):
        """C code to emit in the global section.

        Note that 'frame' (uint8) is available and increments each frame.
        """
        return ''

    def generateSetupCode(self):
        """C code to emit in setup()"""
        return ''

    def generateIdleCode(self):
        """C code to emit in the serial-read loop"""
        return ''

    def generatePollCode(self):
        """
        C code to run a poll update. This should Serial.write its output
        for readFromPoll to consume. If this returns nothing, we don't
        try to poll this device.
        """
        return ''

    def generateActionCode(self):
        """
        If the host side runs sendOutput, this C code will be run on the
        board to receive whatever sendOutput writes. Each sendOutput
        write(buf) call should be matched with len(buf) Serial.read()
        calls in here.
        """
        return ''

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

    def sendOutput(self, statements, write, read):
        """
        If we got statements that match this class's outputPatterns, this
        will be called with the statements that matched, and a serial
        write method. What you write here will be available as
        Serial.read in the generateActionCode C code.

        Todo: it would be fine to read back confirmations or
        whatever. Just need a way to collect them into graph statements.
        """
        raise NotImplementedError

_knownTypes = set()
def register(deviceType):
    _knownTypes.add(deviceType)
    return deviceType

@register
class PingInput(DeviceType):
    @classmethod
    def findInstances(cls, graph, board):
        return [cls(graph, board, None)]

    def generatePollCode(self):
        return "Serial.write('k');"

    def readFromPoll(self, read):
        byte = read(1)
        if byte != 'k':
            raise ValueError('invalid ping response: chr(%s)' % ord(byte))
        return [(self.uri, ROOM['ping'], ROOM['ok'])]

    def watchPrefixes(self):
        return [(self.uri, ROOM['ping'])]

@register
class MotionSensorInput(DeviceType):
    deviceType = ROOM['MotionSensor']
    def __init__(self, graph, uri, pinNumber):
        DeviceType.__init__(self, graph, uri, pinNumber)
        self.lastRead = None

    def generateSetupCode(self):
        return 'pinMode(%(pin)d, INPUT); digitalWrite(%(pin)d, LOW);' % {
            'pin': self.pinNumber,
        }

    def generatePollCode(self):
        return "Serial.write(digitalRead(%(pin)d) ? 'y' : 'n');" % {
            'pin': self.pinNumber
        }

    def readFromPoll(self, read):
        b = read(1)
        if b not in 'yn':
            raise ValueError('unexpected response %r' % b)
        motion = b == 'y'

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
class PushbuttonInput(DeviceType):
    """add a switch to ground; we'll turn on pullup"""
    deviceType = ROOM['Pushbutton']
    def __init__(self, graph, uri, pinNumber):
        DeviceType.__init__(self, graph, uri, pinNumber)
        self.lastClosed = None

    def generateSetupCode(self):
        return 'pinMode(%(pin)d, INPUT); digitalWrite(%(pin)d, HIGH);' % {
            'pin': self.pinNumber,
        }

    def generatePollCode(self):
        # note: pulldown means unpressed reads as a 1
        return "Serial.write(digitalRead(%(pin)d) ? '0' : '1');" % {
            'pin': self.pinNumber
        }

    def readFromPoll(self, read):
        b = read(1)
        if b not in '01':
            raise ValueError('unexpected response %r' % b)
        closed = b == '0'

        if self.lastClosed is not None and closed != self.lastClosed:
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
                'oneshot': oneshot}

    def watchPrefixes(self):
        return [
            (self.uri, ROOM['buttonState']),
        ]

@register
class OneWire(DeviceType):
    """
    A OW bus with temperature sensors (and maybe other devices, which
    are also to be handled under this object). We return graph
    statements for all devices we find, even if we don't scan them, so
    you can more easily add them to your config. Onewire search
    happens only at device startup (not even program startup, yet).

    self.uri is a resource representing the bus.

    DS18S20 pin 1: ground, pin 2: data and pull-up with 4.7k.
    """
    deviceType = ROOM['OneWire']
    pollPeriod = 2
    def hostStateInit(self):
        # eliminate this as part of removing watchPrefixes
        self._knownTempSubjects = set()
    def generateIncludes(self):
        return ['OneWire.h', 'DallasTemperature.h']

    def generateArduinoLibs(self):
        return ['OneWire', 'DallasTemperature']

    def generateGlobalCode(self):
        # not yet isolated to support multiple OW buses
        return '''
OneWire oneWire(%(pinNumber)s);
DallasTemperature sensors(&oneWire);
#define MAX_DEVICES 8
DeviceAddress tempSensorAddress[MAX_DEVICES];

void initSensors() {
  sensors.begin();
  sensors.setResolution(12);
  sensors.setWaitForConversion(false);
  for (uint8_t i=0; i < sensors.getDeviceCount(); ++i) {
    sensors.getAddress(tempSensorAddress[i], i);
  }
}
        ''' % dict(pinNumber=self.pinNumber)

    def generateSetupCode(self):
        return 'initSensors();'

    def generatePollCode(self):
        return r'''
  sensors.requestTemperatures();

  // If we need frequent idle calls or fast polling again, this needs
  // to be changed, but it makes temp sensing work. I had a note that I
  // could just wait until the next cycle to get my reading, but that's
  // not working today, maybe because of a changed poll rate.
  sensors.setWaitForConversion(true); // ~100ms

  Serial.write((uint8_t)sensors.getDeviceCount());
  for (uint8_t i=0; i < sensors.getDeviceCount(); ++i) {
    float newTemp = sensors.getTempF(tempSensorAddress[i]);

    Serial.write(tempSensorAddress[i], 8);
    Serial.write((uint8_t*)(&newTemp), 4);
  }
        '''

    def readFromPoll(self, read):
        t1 = time.time()
        count = ord(read(1))
        stmts = []
        for i in range(count):
            addr = struct.unpack('>Q', read(8))[0]
            tempF = struct.unpack('<f', read(4))[0]
            sensorUri = URIRef(os.path.join(self.uri, 'dev-%s' % hex(addr)[2:]))
            if tempF > 180:
                stmts.extend([
                    (self.uri, ROOM['connectedTo'], sensorUri),
                    (sensorUri, RDF.type, ROOM['FailingTemperatureReading']),
                    ])
                continue
            stmts.extend([
                (self.uri, ROOM['connectedTo'], sensorUri),
                # rounding may be working around a bug where the
                # Literal gets two representations (at different
                # roundings), and this makes an extra value linger on
                # the client.
                (sensorUri, ROOM['temperatureF'], Literal(round(tempF, 2)))])
            self._knownTempSubjects.add(sensorUri)

        log.debug("read temp in %.1fms" % ((time.time() - t1) * 1000))
        return stmts

    def watchPrefixes(self):
        # these uris will become dynamic! see note on watchPrefixes
        # about eliminating it.
        return [(uri, ROOM['temperatureF']) for uri in self._knownTempSubjects]

def byteFromFloat(f):
    return chr(int(min(255, max(0, f * 255))))

@register
class LedOutput(DeviceType):
    deviceType = ROOM['LedOutput']
    def hostStateInit(self):
        self.value = 0

    def generateSetupCode(self):
        return 'pinMode(%(pin)d, OUTPUT); digitalWrite(%(pin)d, LOW);' % {
            'pin': self.pinNumber,
        }

    def outputPatterns(self):
        return [(self.uri, ROOM['brightness'], None)]

    def sendOutput(self, statements, write, read):
        assert len(statements) == 1
        assert statements[0][:2] == (self.uri, ROOM['brightness'])
        self.value = float(statements[0][2])
        if (self.uri, RDF.type, ROOM['ActiveLowOutput']) in self.graph:
            self.value = 1 - self.value
        write(byteFromFloat(self.value))

    def hostStatements(self):
        return [(self.uri, ROOM['brightness'], Literal(self.value))]

    def generateActionCode(self):
        return r'''
          while(Serial.available() < 1) NULL;
          analogWrite(%(pin)d, Serial.read());
        ''' % dict(pin=self.pinNumber)

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
class DigitalOutput(DeviceType):
    deviceType = ROOM['DigitalOutput']
    def hostStateInit(self):
        self.value = 0

    def generateSetupCode(self):
        return 'pinMode(%(pin)d, OUTPUT); digitalWrite(%(pin)d, LOW);' % {
            'pin': self.pinNumber,
        }

    def outputPatterns(self):
        return [(self.uri, ROOM['level'], None)]

    def sendOutput(self, statements, write, read):
        assert len(statements) == 1
        assert statements[0][:2] == (self.uri, ROOM['level'])
        self.value = {"high": 1, "low": 0}[str(statements[0][2])]
        write(chr(self.value))

    def hostStatements(self):
        return [(self.uri, ROOM['level'],
                 Literal('high' if self.value else 'low'))]

    def generateActionCode(self):
        return r'''
          while(Serial.available() < 1) NULL;
          digitalWrite(%(pin)d, Serial.read());
        ''' % dict(pin=self.pinNumber)

    def outputWidgets(self):
        return [{
            'element': 'output-switch',
            'subj': self.uri,
            'pred': ROOM['level'],
        }]


@register
class PwmBoard(DeviceType):
    deviceType = ROOM['PwmBoard']
    @classmethod
    def findInstances(cls, graph, board):
        for row in graph.query("""SELECT DISTINCT ?dev ?sda ?scl WHERE {
          ?board :hasPin ?sdaPin .
          ?board :hasPin ?sclPin .
          ?sdaPin :pinNumber ?sda; :connectedTo ?sdaConn .
          ?sclPin :pinNumber ?scl; :connectedTo ?sclConn .
          ?dev a :PwmBoard;
            :scl ?sclConn;
            :sda ?sdaConn .
        }""", initBindings=dict(board=board), initNs={'': ROOM}):
            if (row.sda, row.scl) != (Literal('a4'), Literal('a5')):
                raise NotImplementedError(row)
            outs = {}
            for out in graph.query("""SELECT DISTINCT ?area ?chan WHERE {
               ?dev :output [:area ?area; :channel ?chan] .
            }""", initBindings=dict(dev=row.dev), initNs={'': ROOM}):
                outs[out.area] = out.chan.toPython()
            yield cls(graph, row.dev, outs=outs)

    def __init__(self, graph, dev, outs):
        self.codeVals = {'pwm': 'pwm%s' % (hash(str(dev)) % 99999)}
        self.outs = outs
        super(PwmBoard, self).__init__(graph, dev, pinNumber=None)

    def hostStateInit(self):
        self.values = {uri: 0 for uri in self.outs.keys()} # uri: brightness

    def hostStatements(self):
        return [(uri, ROOM['brightness'], Literal(b))
                for uri, b in self.values.items()]

    def generateIncludes(self):
        return ['Wire.h', 'Adafruit_PWMServoDriver.h']

    def generateArduinoLibs(self):
        return ['Wire', 'Adafruit-PWM-Servo-Driver-Library']

    def generateGlobalCode(self):
        return r'''
          Adafruit_PWMServoDriver %(pwm)s = Adafruit_PWMServoDriver(0x40);
        ''' % self.codeVals

    def generateSetupCode(self):
        return '''
          %(pwm)s.begin();
          %(pwm)s.setPWMFreq(1200);
        ''' % self.codeVals

    def generateActionCode(self):
        return r'''
          while(Serial.available() < 3) NULL;
          byte chan = Serial.read();
          uint16_t level = uint16_t(Serial.read()) << 8;
          level |= Serial.read();
          %(pwm)s.setPWM(chan, 0, level);
        ''' % self.codeVals

    def outputPatterns(self):
        return [(area, ROOM['brightness'], None) for area in self.outs]

    def sendOutput(self, statements, write, read):
        assert len(statements) == 1
        assert statements[0][1] == ROOM['brightness'];
        chan = self.outs[statements[0][0]]
        value = float(statements[0][2])
        self.values[statements[0][0]] = value
        v12 = int(min(4095, max(0, value * 4095)))
        write(chr(chan) + chr(v12 >> 8) + chr(v12 & 0xff))

    def outputWidgets(self):
        return [{
            'element': 'output-slider',
            'min': 0,
            'max': 1,
            'step': 1 / 255,
            'subj': area,
            'pred': ROOM['brightness'],
        } for area in self.outs]

@register
class ST7576Lcd(DeviceType):
    deviceType = ROOM['ST7565Lcd']
    @classmethod
    def findInstances(cls, graph, board):
        grouped = itertools.groupby(
            graph.query("""SELECT DISTINCT ?dev ?pred ?pinNumber WHERE {
                                    ?board :hasPin ?pin .
                                    ?pin :pinNumber ?pinNumber;
                                         :connectedTo ?devPin .
                                    ?dev a :ST7565Lcd .
                                    ?dev ?pred ?devPin .
                                  } ORDER BY ?dev""",
                               initBindings=dict(board=board,
                                                 thisType=cls.deviceType),
                               initNs={'': ROOM}),
            lambda row: row.dev)
        for dev, connections in grouped:
            connections = dict((role, int(num)) for unused_dev, role, num
                               in connections)
            yield cls(graph, dev, connections=connections)

    def __init__(self, graph, dev, connections):
        super(ST7576Lcd, self).__init__(graph, dev, pinNumber=None)
        self.connections = connections
        self.text = ''

    def generateIncludes(self):
        return ['ST7565.h']

    def generateArduinoLibs(self):
        return ['ST7565']

    def generateGlobalCode(self):
        return '''
          ST7565 glcd(%(SID)d, %(SCLK)d, %(A0)d, %(RST)d, %(CS)d);
          char newtxt[21*8+1];
          unsigned int written;
        ''' % dict(SID=self.connections[ROOM['lcdSID']],
                   SCLK=self.connections[ROOM['lcdSCLK']],
                   A0=self.connections[ROOM['lcdA0']],
                   RST=self.connections[ROOM['lcdRST']],
                   CS=self.connections[ROOM['lcdCS']])

    def generateSetupCode(self):
        return '''
          glcd.st7565_init();
          glcd.st7565_command(CMD_DISPLAY_ON);
          glcd.st7565_command(CMD_SET_ALLPTS_NORMAL);
          glcd.st7565_set_brightness(0x18);

          glcd.display(); // show splashscreen
        '''

    def outputPatterns(self):
        return [(self.uri, ROOM['text'], None)]

    def sendOutput(self, statements, write, read):
        assert len(statements) == 1
        assert statements[0][:2] == (self.uri, ROOM['text'])
        self.text = str(statements[0][2])
        assert len(self.text) < 254, repr(self.text)
        write(chr(len(self.text)) + self.text)

    def hostStatements(self):
        return [(self.uri, ROOM['text'], Literal(self.text))]

    def outputWidgets(self):
        return [{
                'element': 'output-fixed-text',
                'cols': 21,
                'rows': 8,
                'subj': self.uri,
                'pred': ROOM['text'],
            }]

    def generateActionCode(self):
        return '''
          while(Serial.available() < 1) NULL;
          byte bufSize = Serial.read();
          for (byte i = 0; i < bufSize; ++i) {
            while(Serial.available() < 1) NULL;
            newtxt[i] = Serial.read();
          }
          for (byte i = bufSize; i < sizeof(newtxt); ++i) {
            newtxt[i] = 0;
          }
          glcd.clear();
          glcd.drawstring(0,0, newtxt);
          glcd.display();
        '''

@register
class RgbPixels(DeviceType):
    """chain of FastLED-controllable rgb pixels"""
    deviceType = ROOM['RgbPixels']

    def __init__(self, graph, uri, pinNumber):
        super(RgbPixels, self).__init__(graph, uri, pinNumber)
        self.anim = RgbPixelsAnimation(graph, uri, self.updateOutput)

        self.replace = {'ledArray': 'leds_%s' % self.pinNumber,
                        'ledCount': self.anim.maxIndex() - 1,
                        'pin': self.pinNumber,
                        'ledType': 'WS2812',
        }

    def generateIncludes(self):
        """filenames of .h files to #include"""
        return ['FastLED.h']

    def generateArduinoLibs(self):
        """names of libraries for the ARDUINO_LIBS line in the makefile"""
        return ['FastLED-3.1.0']

    def myId(self):
        return 'rgb_%s' % self.pinNumber

    def generateGlobalCode(self):
        return 'CRGB {ledArray}[{ledCount}];'.format(**self.replace)

    def generateSetupCode(self):
        return 'FastLED.addLeds<{ledType}, {pin}>({ledArray}, {ledCount});'.format(**self.replace)

    def sendOutput(self, statements, write, read):
        log.info('sendOutput start')
        self.write = write
        self.anim.onStatements(statements)
        self.anim.updateOutput()
        log.info('sendOutput end')

    def updateOutput(self):
        write = self.write
        write(chr(self.anim.maxIndex() + 1))
        for idx, (r, g, b) in self.anim.currentColors():
            # my WS2812 need these flipped
            write(chr(idx) + chr(g) + chr(r) + chr(b))

    def wantIdleOutput(self):
        return True

    def outputIdle(self, write):
        self.write = write
        self.updateOutput()

    def hostStatements(self):
        return self.anim.hostStatements()

    def outputPatterns(self):
        return self.anim.outputPatterns()

    def outputWidgets(self):
        return self.anim.outputWidgets()

    def generateActionCode(self):
        # not yet combining updates- may be slow
        return '''
        while(Serial.available() < 1) NULL;
byte count = Serial.read();
       for (byte elt=0; elt<count; ++elt) {{
          while(Serial.available() < 1) NULL;
          byte id = Serial.read();

          while(Serial.available() < 1) NULL;
          byte r = Serial.read();

          while(Serial.available() < 1) NULL;
          byte g = Serial.read();

          while(Serial.available() < 1) NULL;
          byte b = Serial.read();

        {ledArray}[id] = CRGB(r, g, b);
        }}
        FastLED.show();

        '''.format(**self.replace)

def makeDevices(graph, board):
    out = []
    for dt in sorted(_knownTypes, key=lambda cls: cls.__name__):
        out.extend(dt.findInstances(graph, board))
    return out
