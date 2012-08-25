#!bin/python
"""
talks to frontdoordriver.pde on an arduino
"""

from __future__ import division

import cyclone.web, json, traceback, os, sys, time, logging, bitstring
from twisted.internet import reactor, task, defer
from twisted.web.client import getPage
sys.path.append("/my/proj/house/frontdoor")
from loggingserial import LoggingSerial        
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log
sys.path.append("../../../room")
from carbondata import CarbonClient
sys.path.append("/my/site/magma")
from stategraph import StateGraph      
from rdflib import Namespace, RDF, Literal
from webcolors import hex_to_rgb, rgb_to_hex

def rgbFromHex(h):
    """returns tuple of 0..1023"""
    norm = hex_to_rgb(h)
    return tuple([x * 4 for x in norm])

def hexFromRgb(rgb):
    return rgb_to_hex(tuple([x // 4 for x in rgb]))


ROOM = Namespace("http://projects.bigasterisk.com/room/")
DEV = Namespace("http://projects.bigasterisk.com/device/")

class ArduinoGarage(object):
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
        return ret

    def lastLevel(self):
        self.ser.write("\x60\x02\x00")
        return self.ser.readJson()['z']

    def setThreshold(self, t):
        """set 10-bit threshold"""
        self.ser.write("\x60\x03"+chr(max(1 << 2, t) >> 2))
        return self.ser.readJson()['threshold']

    def setGarage(self, level):
        """set garage door opener pin"""
        self.ser.write("\x60\x04"+chr(int(bool(level))))
        return self.ser.readJson()['garage']

    def setVideoSelect(self, chan):
        """set video select bits from 0..3"""
        self.ser.write("\x60\x05"+chr(chan))
        return self.ser.readJson()['videoSelect']

    def shiftbrite(self, colors):
        """
        shift out this sequence of (r,g,b) triples of 10-bit ints
        """
        resetCurrent = "".join(bitstring.pack("0b01, uint:10, uint:10, uint:10",
                                              127, 127, 127).bytes
                               for loop in range(len(colors)))
        out = "".join(bitstring.pack("0b00, uint:10, uint:10, uint:10",
                                     b, r, g).bytes
                      for r,g,b in colors)
        out = resetCurrent + out
        self.ser.write("\x60\x06" + chr(len(out)) + out)
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

class GraphPage(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/x-trig")
        g = StateGraph(ROOM['garageArduino'])
        self.settings.poller.assertIsCurrent()
        g.add((DEV['frontDoorMotion'], ROOM['state'],
               ROOM['motion'] if self.settings.poller.lastValues['motion'] else
               ROOM['noMotion']))
        g.add((ROOM['house'], ROOM['usingPower'],
               Literal(self.settings.poller.lastWatts, datatype=ROOM["#watts"])))
        self.write(g.asTrig())

class FrontDoorMotion(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/javascript")
        self.settings.poller.assertIsCurrent()
        self.write(json.dumps({"frontDoorMotion" :
                               self.settings.poller.lastValues['motion']}))

class HousePower(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/javascript")
        self.settings.poller.assertIsCurrent()
        w = self.settings.poller
        self.write(json.dumps({
            "currentWatts" : round(w.lastWatts, 2) if isinstance(w.lastWatts, float) else w.lastWatts,
            "lastPulseAgo" : "%.1f sec ago" % (time.time() - w.lastBlinkTime) if w.lastBlinkTime is not None else "unknown",
            "kwhPerBlink" : w.kwhPerBlink}))

class HousePowerRaw(PrettyErrorHandler, cyclone.web.RequestHandler):
    """
    raw data from the analog sensor, for plotting or picking a noise threshold
    """
    def get(self):
        self.set_header("Content-Type", "application/javascript")
        pts = []
        for i in range(60):
            level = self.settings.arduino.lastLevel()
            pts.append((round(time.time(), 3), level))

        self.write(json.dumps({"irLevels" : pts}))

class HousePowerThreshold(PrettyErrorHandler, cyclone.web.RequestHandler):
    """
    the level that's between between an IR pulse and the noise
    """
    def get(self):
        self.set_header("Content-Type", "application/javascript")
        self.settings.poller.assertIsCurrent()
        self.write(json.dumps({"threshold" : thr}))
        
    def put(self):
        pass

class GarageDoorOpen(PrettyErrorHandler, cyclone.web.RequestHandler):
    def post(self):
        self.set_header("Content-Type", "text/plain")
        self.settings.arduino.setGarage(True)
        self.write("pin high, waiting..\n")
        self.flush()
        d = defer.Deferred()
        def finish():
            self.settings.arduino.setGarage(False)            
            self.write("pin low. Done")
            d.callback(None)
        reactor.callLater(1.5, finish) # this time depends on the LP circuit
        return d

class VideoSelect(PrettyErrorHandler, cyclone.web.RequestHandler):
    def post(self): 
        self.set_header("Content-Type", "application/javascript")
        v = self.settings.arduino.setVideoSelect(int(self.request.body))
        self.write(json.dumps({"videoSelect" : v}))

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
    def __init__(self, ard, poller):
        handlers = [
            (r"/", Index),
            (r"/graph", GraphPage),
            (r"/frontDoorMotion", FrontDoorMotion),
            (r'/housePower', HousePower),
            (r'/housePower/raw', HousePowerRaw),
            (r'/housePower/threshold', HousePowerThreshold),
            (r'/garageDoorOpen', GarageDoorOpen),
            (r'/videoSelect', VideoSelect), 
            (r"/brite/(\d+)", Brite),
        ]
        colors = [(0,0,0)] * 1 # stored 10-bit
        settings = {"arduino" : ard, "poller" : poller, "colors" : colors}
        cyclone.web.Application.__init__(self, handlers, **settings)

class Poller(object):
    """
    times the blinks to estimate power usage. Captures the other
    returned sensor values too in self.lastValues
    """
    def __init__(self, ard, period):
        self.ard = ard
        self.period = period
        self.carbon = CarbonClient(serverHost='bang')
        self.lastBlinkTime = None
        self.lastValues = None
        self.lastPollTime = 0
        self.lastWatts = "(just restarted; wait no data yet)"
        self.kwhPerBlink = 1.0 # unsure
        self.lastMotion = False

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
                self.lastPollTime = now
                self.lastValues = newData # for other data besides the blinks
                self.processBlinks(now, newData['newBlinks'])
                self.processMotion(newData['motion'])
            
        except (IOError, OSError):
            os.abort()
        except Exception, e:
            print "poll error", e
            traceback.print_exc()

    def processBlinks(self, now, b):
        if b > 0:
            if b > 1:
                # todo: if it's like 1,1,2,2,2,2,1,1 then we
                # need to subdivide those inner sample periods
                # since there might really be two blinks. But
                # if it's like 0,0,0,2,0,0, that should be
                # treated like b=1 since it's probably noise
                pass

            if self.lastBlinkTime is not None:
                dt = now - self.lastBlinkTime
                dth = dt / 3600.
                watts = self.kwhPerBlink / dth

                if watts > 10000:
                    # this pulse (or the previous one) is
                    # likely noise. Too late for the previous
                    # one, but we're going to skip this one
                    return
                else:
                    self.lastWatts = watts

                    # todo: remove this; a separate logger shall do it
                    self.carbon.send('system.house.powerMeter_w', watts, now)

            self.lastBlinkTime = now

    def processMotion(self, state):
        if state == self.lastMotion:
            return
        self.lastMotion = state
        msg = json.dumps(dict(board='garage', 
                              name="frontDoorMotion", state=state))
        getPage('http://bang.bigasterisk.com:9069/inputChange',
                method="POST",
                postdata=msg,
                headers={'Content-Type' : 'application/json'}
                ).addErrback(self.reportError, msg)

    def reportError(self, msg, *args):
        print "post error", msg, args

if __name__ == '__main__':

    config = { # to be read from a file
        'arduinoPort': '/dev/serial/by-id/usb-Arduino__www.arduino.cc__Arduino_Uno_6493534323335161A2F1-if00',
        'servePort' : 9050,
        'pollFrequency' : 5,
        'boardName' : 'garage', # gets sent with updates
        }

    #from twisted.python import log as twlog
    #twlog.startLogging(sys.stdout)

    log.setLevel(logging.DEBUG)

    ard = ArduinoGarage(port=config['arduinoPort'])

    period = 1/config['pollFrequency']
    p = Poller(ard, period)
    task.LoopingCall(p.poll).start(period)
    reactor.listenTCP(config['servePort'], Application(ard, p))
    reactor.run()
