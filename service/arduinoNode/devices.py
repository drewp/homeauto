from __future__ import division
import itertools
from rdflib import Namespace, RDF, URIRef, Literal

ROOM = Namespace('http://projects.bigasterisk.com/room/')
XSD = Namespace('http://www.w3.org/2001/XMLSchema#')

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
            yield cls(graph, row.dev, int(row.pinNumber))

    # subclasses may add args to this
    def __init__(self, graph, uri, pinNumber):
        self.graph, self.uri = graph, uri
        self.pinNumber = pinNumber
        
    def readFromPoll(self, read):
        """
        read an update message returned as part of a poll bundle. This may
        consume a varying number of bytes depending on the type of
        input (e.g. IR receiver).
        Returns rdf statements.
        """
        raise NotImplementedError('readFromPoll in %s' % self.__class__)

    def generateIncludes(self):
        return []

    def generateArduinoLibs(self):
        return []
        
    def generateGlobalCode(self):
        return ''
        
    def generateSetupCode(self):
        return ''
        
    def generatePollCode(self):
        """if this returns nothing, we don't try to poll this device"""
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
        if read(1) != 'k':
            raise ValueError('invalid ping response')
        return [(self.uri, ROOM['ping'], ROOM['ok'])]

@register
class MotionSensorInput(DeviceType):
    deviceType = ROOM['MotionSensor']
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
        return [(self.uri, ROOM['sees'],
                 ROOM['motion'] if motion else ROOM['noMotion'])]

@register
class OneWire(DeviceType):
    deviceType = ROOM['OneWire']
   
    def generateIncludes(self):
        return ['OneWire.h', 'DallasTemperature.h']

    def generateArduinoLibs(self):
        return ['OneWire', 'DallasTemperature']
        
    def generateGlobalCode(self):
        # not yet isolated to support multiple OW buses
        return '''
OneWire oneWire(%(pinNumber)s); 
DallasTemperature sensors(&oneWire);
DeviceAddress tempSensorAddress;
#define NUM_TEMPERATURE_RETRIES 2

void initSensors() {
  sensors.begin();
  sensors.getAddress(tempSensorAddress, 0);
  sensors.setResolution(tempSensorAddress, 12);
}
        ''' % dict(pinNumber=self.pinNumber)
        
    def generatePollCode(self):
        return r'''
for (int i=0; i<NUM_TEMPERATURE_RETRIES; i++) {
  sensors.requestTemperatures();
  float newTemp = sensors.getTempF(tempSensorAddress);
  if (i < NUM_TEMPERATURE_RETRIES-1 && 
      (newTemp < -100 || newTemp > 180)) {
    // too many errors that were fixed by restarting arduino. 
    // trying repeating this much init
    initSensors();
    continue;
  }
  Serial.print(newTemp);
  Serial.print('\n');
  Serial.print((char)i);
  break;
}
        '''

    def readFromPoll(self, read):
        newTemp = readLine(read)
        retries = ord(read(1))
        return [
            (self.uri, ROOM['temperatureF'],
             Literal(newTemp, datatype=XSD['decimal'])),
            (self.uri, ROOM['temperatureRetries'], Literal(retries)),
            ]

def byteFromFloat(f):
    return chr(int(min(255, max(0, f * 255))))
        
@register
class LedOutput(DeviceType):
    deviceType = ROOM['LedOutput']
    def generateSetupCode(self):
        return 'pinMode(%(pin)d, OUTPUT); digitalWrite(%(pin)d, LOW);' % {
            'pin': self.pinNumber,
        }
 
    def outputPatterns(self):
        return [(self.uri, ROOM['brightness'], None)]

    def sendOutput(self, statements, write, read):
        assert len(statements) == 1
        assert statements[0][:2] == (self.uri, ROOM['brightness'])
        value = float(statements[0][2])
        if (self.uri, RDF.type, ROOM['ActiveLowOutput']):
            value = 1 - value
        write(byteFromFloat(value))
        
    def generateActionCode(self):
        return r'''
          while(Serial.available() < 1) NULL;
          analogWrite(%(pin)d, Serial.read());
        ''' % dict(pin=self.pinNumber)
        
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
        value = str(statements[0][2])
        assert len(value) < 254, repr(value)
        write(chr(len(value)) + value)

    def generateActionCode(self):
        return '''
          while(Serial.available() < 1) NULL;
          byte bufSize = Serial.read();
          for (byte i = 0; i < bufSize; i++) {
            while(Serial.available() < 1) NULL;
            newtxt[i] = Serial.read();
          }
          glcd.clear();
          glcd.drawstring(0,0, newtxt); 
          glcd.display();
        '''

def makeDevices(graph, board):
    out = []
    for dt in sorted(_knownTypes, key=lambda cls: cls.__name__):
        out.extend(dt.findInstances(graph, board))
    return out
        
