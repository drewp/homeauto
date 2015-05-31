from __future__ import division
import pigpio
import time
from rdflib import Namespace, RDF, URIRef, Literal

ROOM = Namespace('http://projects.bigasterisk.com/room/')

class DeviceType(object):
    deviceType = None
    @classmethod
    def findInstances(cls, graph, board, pi):
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
            yield cls(graph, row.dev, pi, int(row.pinNumber))

    def __init__(self, graph, uri, pi, pinNumber):
        self.graph, self.uri, self.pi = graph, uri, pi
        self.pinNumber = pinNumber

    def description(self):
        return {
            'uri': self.uri,
            'className': self.__class__.__name__,
            'pinNumber': self.pinNumber,
            'outputPatterns': self.outputPatterns(),
            'watchPrefixes': self.watchPrefixes(),
            'outputWidgets': self.outputWidgets(),
        }

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

def makeDevices(graph, board, pi):
    out = []
    for dt in sorted(_knownTypes, key=lambda cls: cls.__name__):
        out.extend(dt.findInstances(graph, board, pi))
    return out
        
