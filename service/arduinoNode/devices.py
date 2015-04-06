from rdflib import Namespace, RDF, URIRef

ROOM = Namespace('http://projects.bigasterisk.com/room/')

class BoardInput(object):
    """
    one device that gives us input. this includes processing to make
    statements, but this object doesn't store state
    """
    def __init__(self, graph, uri):
        self.graph, self.uri = graph, uri
        
    def readFromPoll(self, read):
        """
        read an update message returned as part of a poll bundle. This may
        consume a varying number of bytes depending on the type of
        input (e.g. IR receiver).
        Returns rdf statements.
        """
        raise NotImplementedError

    def generateSetupCode(self):
        return ''
        
    def generatePollCode(self):
        return ''

    def pinNumber(self, pred=ROOM['pin']):
        pinUri = self.graph.value(self.uri, pred)
        return int(self.graph.value(pinUri, ROOM['pinNumber']))

_inputForType = {}
def registerInput(deviceType):
    def newcls(cls):
        _inputForType[deviceType] = cls
        return cls
    return newcls
        
class PingInput(BoardInput):
    def generatePollCode(self):
        return "Serial.write('k');"
    def readFromPoll(self, read):
        if read(1) != 'k':
            raise ValueError('invalid ping response')
        return [(self.uri, ROOM['ping'], ROOM['ok'])]

@registerInput(deviceType=ROOM['MotionSensor'])
class MotionSensorInput(BoardInput):
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

def makeBoardInput(graph, uri):
    deviceType = graph.value(uri, RDF.type)
    return _inputForType[deviceType](graph, uri)
        
