#!bin/python
"""
talks to bed.pde on an arduino
"""

from __future__ import division

import cyclone.web, json, traceback, os, sys, time, logging, bitstring
from twisted.internet import reactor, task
from twisted.web.client import getPage
sys.path.append("/my/proj/house/frontdoor")
from loggingserial import LoggingSerial        
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

sys.path.append("/my/proj/pixel/shiftweb")
from shiftweb import hexFromRgb, rgbFromHex

sys.path.append("/my/site/magma")
from stategraph import StateGraph      
from rdflib import Namespace

ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")

class ArduinoBedroom(object):
    def __init__(self, port='/dev/ttyACM0'):
        self.ser = LoggingSerial(port=port, baudrate=115200, timeout=1)
        self.ser.flush()

    def ping(self):
        self.ser.write("\x60\x00\x00")
        msg = self.ser.readJson()
        assert msg == {"ok":True}, msg

    def poll(self):
        self.ser.write("\x60\x01\x00")
        ret = self.ser.readJson()
        ret['motion'] = int(ret['motion'] > 100)
        return ret

    def setSpeakerChoice(self, pillow):
        self.ser.write("\x60\x02" + chr(pillow))
        return self.ser.readJson()

    def setLeds(self, colors):
        """
        shift out this sequence of (r,g,b) triples of 10-bit ints
        The nearest led gets color[0], etc.
        """
        resetCurrent = "".join(bitstring.pack("0b01, uint:10, uint:10, uint:10",
                                              127, 127, 127).bytes
                               for loop in range(len(colors)))
        out = "".join(bitstring.pack("0b00, uint:10, uint:10, uint:10",
                                     b, r, g).bytes
                      for r,g,b in reversed(colors))
        out = resetCurrent + out
        self.ser.write("\x60\x03" + chr(len(out)) + out)
        msg = self.ser.readJson()
        assert msg == {"ok":1}, msg

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        """
        this is an acceptable status check since it makes a round-trip
        to the arduino before returning success
        """
        self.settings.arduino.ping()
        
        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(open("index.html").read())

class SpeakerChoice(PrettyErrorHandler, cyclone.web.RequestHandler):
    def put(self):
        ret = self.settings.arduino.setSpeakerChoice(int(self.get_argument('pillow')))
        self.write(ret)

class Brite(PrettyErrorHandler, cyclone.web.RequestHandler):
    def put(self, which):
        which = int(which)
        brites = self.settings.brites
        if which + 1 > len(brites):
            brites.extend([(0,0,0)] * (which + 1 - len(brites)))
        brites[which] = rgbFromHex(self.request.body)
                          
        self.settings.arduino.setLeds(brites)
        self.set_header("Content-Type", "text/plain")
        self.write("ok")

class GraphPage(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/x-trig")
        g = StateGraph(ROOM['bedroomArduino'])
        self.settings.poller.assertIsCurrent()
        g.add((DEV['bedroomMotion'], ROOM['state'],
               ROOM['motion'] if self.settings.poller.lastValues['motion'] else
               ROOM['noMotion']))
        self.write(g.asTrig())

class Poller(object):
    """
    Watches sensor values
    """
    def __init__(self, config, ard, period):
        self.config, self.ard = config, ard
        self.period = period
        self.lastValues = None
        self.lastPollTime = 0
        self.lastMotion = None

    def assertIsCurrent(self):
        """raise an error if the poll data is not fresh"""
        dt = time.time() - self.lastPollTime
        if dt > period * 2:
            raise ValueError("last poll time was too old: %.1f sec ago" % dt)
    
    def poll(self):
        now = time.time()
        try:
            try:
                newData = ard.poll()
            except ValueError, e:
                print e
            else:
                #print newData # for testing

                self.lastPollTime = now
                self.lastValues = newData # for other data besides the blinks
                self.processMotion(newData['motion'])
            
        except (IOError, OSError):
            os.abort()
        except Exception, e:
            print "poll error", e
            traceback.print_exc()

    def processMotion(self, state):
        if state == self.lastMotion:
            return
        self.lastMotion = state
        msg = json.dumps(dict(board=self.config['boardName'], 
                              name="bedroomMotion", state=state))
        getPage('http://bang.bigasterisk.com:9069/inputChange',
                method="POST",
                postdata=msg,
                headers={'Content-Type' : 'application/json'}
                ).addErrback(self.reportError, msg)

    def reportError(self, msg, *args):
        print "post error", msg, args

if __name__ == '__main__':

    config = { # to be read from a file
        'arduinoPort': '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A4001nIu-if00-port0',
        'servePort' : 9088,
        'pollFrequency' : 6,
        'boardName' : 'bedroom', # gets sent with updates
        }

    from twisted.python import log as twlog
    #twlog.startLogging(sys.stdout)

    log.setLevel(logging.DEBUG)

    ard = ArduinoBedroom(port=config['arduinoPort'])

    period = 1/config['pollFrequency']
    p = Poller(config, ard, period)
    task.LoopingCall(p.poll).start(period)

    reactor.listenTCP(config['servePort'], cyclone.web.Application([
        (r"/", Index),
        (r"/graph", GraphPage),
        (r'/speakerChoice', SpeakerChoice),
        (r'/brite/(\d+)', Brite),
        ], arduino=ard, poller=p, brites=[]))
    reactor.run()