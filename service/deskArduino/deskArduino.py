#!bin/python
"""
talks to shiftbrite driver on dash, plus future arduino stuff
"""

from __future__ import division

import cyclone.web, sys, bitstring
from twisted.python import log
from twisted.internet import reactor
from rdflib import Namespace
sys.path.append("/my/proj/house/frontdoor")
from loggingserial import LoggingSerial        
sys.path.append("/my/site/magma")
from stategraph import StateGraph      
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")

from webcolors import hex_to_rgb, rgb_to_hex

def rgbFromHex(h):
    """returns tuple of 0..1023"""
    norm = hex_to_rgb(h)
    return tuple([x * 4 for x in norm])

def hexFromRgb(rgb):
    return rgb_to_hex(tuple([x // 4 for x in rgb]))

class ArduinoDesk(object):
    def __init__(self, ports=['/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A900gbcG-if00-port0']):
        self.ser = LoggingSerial(ports=ports, baudrate=115200, timeout=1)

    def ping(self):
        self.ser.write("\x60\x00")
        msg = self.ser.readJson()
        assert msg == {"ok":"ping"}, msg

    def shiftbrite(self, colors):
        """
        shift out this sequence of (r,g,b) triples of 10-bit ints
        """
        out = "".join(bitstring.pack("0b00, uint:10, uint:10, uint:10",
                                     b, r, g).bytes
                      for r,g,b in colors)

        self.ser.write("\x60\x01" + chr(len(out)) + out)
        msg = self.ser.readJson()
        assert msg == {"ok":1}, msg
        
class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.settings.arduino.ping()
        
        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(open("index.html").read())

class GraphPage(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/x-trig")
        g = StateGraph(ROOM['deskArduino'])
        # g.add((s,p,o)) for colors and stuff      
        self.write(g.asTrig())

class Brite(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self, chan):
        self.set_header("Content-Type", "text/plain")
        self.write(hexFromRgb(self.settings.colors[int(chan)]))
        
    def put(self, chan):
        s = self.settings
        s.colors[int(chan)] = rgbFromHex(self.request.body)
        s.arduino.shiftbrite(s.colors)
    post = put

class Application(cyclone.web.Application):
    def __init__(self, arduino):
        handlers = [
            (r"/", Index),
            (r"/graph", GraphPage),
            (r"/brite/(\d+)", Brite),
        ]
        colors = [(0,0,0)] * 2 # stored 10-bit
        cyclone.web.Application.__init__(self, handlers,
                                         arduino=arduino, colors=colors)

if __name__ == '__main__':
    config = { # to be read from a file
        'servePort' : 9014,
        }

    #log.startLogging(sys.stdout)

    arduino = ArduinoDesk()

    reactor.listenTCP(config['servePort'], Application(arduino))
    reactor.run()
