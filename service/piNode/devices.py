from __future__ import division

import time, logging
from rdflib import Namespace, RDF, URIRef, Literal

try:
    import pigpio
except ImportError:
    pigpio = None
    

log = logging.getLogger()
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
        for row in graph.query("""SELECT ?dev ?gpioNumber WHERE {
                                    ?board :hasPin ?pin .
                                    ?pin :gpioNumber ?gpioNumber;
                                         :connectedTo ?dev .
                                    ?dev a ?thisType .
                                  } ORDER BY ?dev""",
                               initBindings=dict(board=board,
                                                 thisType=cls.deviceType),
                               initNs={'': ROOM}):
            yield cls(graph, row.dev, pi, int(row.gpioNumber))

    def __init__(self, graph, uri, pi, pinNumber):
        self.graph, self.uri, self.pi = graph, uri, pi
        self.pinNumber = pinNumber

    def description(self):
        return {
            'uri': self.uri,
            'className': self.__class__.__name__,
            'pinNumber': getattr(self, 'pinNumber', None),
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


@register
class RgbStrip(DeviceType):
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
            
    def setup(self):
        for i in self.rgb:
            self.pi.set_mode(i, pigpio.OUTPUT)
            self.pi.set_PWM_frequency(i, 200)
            self.pi.set_PWM_dutycycle(i, 0)

    def outputPatterns(self):
        return [(self.uri, ROOM['color'], None)]
    
    def sendOutput(self, statements):
        assert len(statements) == 1
        assert statements[0][:2] == (self.uri, ROOM['color'])

        rrggbb = statements[0][2].lstrip('#')
        rgb = [int(x, 16) for x in [rrggbb[0:2], rrggbb[2:4], rrggbb[4:6]]]

        for (i, v) in zip(self.rgb, rgb):
            self.pi.set_PWM_dutycycle(i, v)
        
    def outputWidgets(self):
        return [{
            'element': 'output-rgb',
            'subj': self.uri,
            'pred': ROOM['color'],
        }]

@register
class OnboardTemperature(DeviceType):
    deviceType = ROOM['OnboardTemperature']
    @classmethod
    def findInstances(cls, graph, board, pi):
        for row in graph.query('''SELECT DISTINCT ?dev WHERE {
          ?board :onboardDevice ?uri . 
          ?uri a :OnboardTemperature .
        }'''):
            yield cls(graph, row.uri, pi, pinNumber=None)
    
    def readFromPoll(self):
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
        
