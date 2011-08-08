"""
arduino driver for the nightlight+buttons+temp setup running on star

"""
from __future__ import division

import sys, jsonlib
from twisted.internet import reactor, task
import cyclone.web

sys.path.append("/my/proj/pixel/shiftweb")
from drvarduino import ShiftbriteArduino
from shiftweb import hexFromRgb, rgbFromHex

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

sys.path.append("/my/proj/ariremote")
from oscserver import ArduinoWatcher

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.settings.arduino.ping()
        
        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(open("index.html").read())

class Temperature(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        f = self.settings.arduino.getTemperature()
        self.set_header("Content-Type", "application/json")
        self.write(jsonlib.write({"temp" : f}))

class Brite(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self, pos):
        self.set_header("Content-Type", "text/plain")
        self.write(hexFromRgb(self.settings.colors[int(pos)]))

    def put(self, pos):
        channel = int(pos)
        colors = self.settings.colors
        colors[channel] = rgbFromHex(self.request.body)
        self.settings.arduino.update(colors)
        self.set_header("Content-Type", "text/plain")
        self.write("updated %r" % colors)
    
class Graph(PrettyErrorHandler, cyclone.web.RequestHandler):    
    def get(self):
        raise NotImplementedError
    
if __name__ == '__main__':
    sb = ShiftbriteArduino(numChannels=3)

    colors = [(0,0,0)] * sb.numChannels

    aw = ArduinoWatcher(sb)
    task.LoopingCall(aw.poll).start(1.0/20)
    
    reactor.listenTCP(9014, cyclone.web.Application([
        (r'/', Index),
        (r'/temperature', Temperature),
        (r'/brite/(\d+)', Brite),
        (r'/graph', Graph),
        ], arduino=sb, colors=colors))
    reactor.run()
