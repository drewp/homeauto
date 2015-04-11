from rdflib import Namespace, RDF, URIRef, Literal

ROOM = Namespace('http://projects.bigasterisk.com/room/')

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
        instances = []
        for row in graph.query("""SELECT ?dev ?pinNumber WHERE {
                                    ?board :hasPin ?pin .
                                    ?pin :pinNumber ?pinNumber;
                                         :connectedTo ?dev .
                                    ?dev a ?thisType .
                                  } ORDER BY ?dev""",
                               initBindings=dict(board=board,
                                                 thisType=cls.deviceType),
                               initNs={'': ROOM}):
            instances.append(cls(graph, row.dev, int(row.pinNumber)))
        return instances

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
        if you get called to do your action, this code reads the args you
        need and do the right action
        """
        return ''
       
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
            'pin': self.pinNumber(),
        }
        
    def generatePollCode(self):
        return "Serial.write(digitalRead(%(pin)d) ? 'y' : 'n');" % {
            'pin': self.pinNumber()
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
#define NUM_TEMPERATURE_RETRIES 5

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
            (self.uri, ROOM['temperatureF'], Literal(newTemp)),
            (self.uri, ROOM['temperatureRetries'], Literal(retries)),
            ]

def makeDevices(graph, board):
    out = []
    for dt in sorted(_knownTypes, key=lambda cls: cls.__name__):
        out.extend(dt.findInstances(graph, board))
    return out
        