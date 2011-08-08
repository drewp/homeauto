"""
arduino example sketches, 'StandardFirmata'.

####easy_install http://github.com/lupeke/python-firmata/tarball/master

Now using http://code.google.com/p/pyduino, modified to run at 57600
baud like my arduino's code does. pyduino is better than the lupeke
one in that you can read your settings off the output pins

Note that there are some startup delays and you may not hear about
input changes for a few seconds.
"""
from __future__ import division
import sys, cyclone.web, time, simplejson, os
from twisted.web.client import getPage
from twisted.internet import reactor, task

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

sys.path.append("pyduino-read-only")
import pyduino 

def _num(name):
    if name.startswith('d'):
        return int(name[1:])
    raise ValueError(name)
                         
class pin(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self, name):
        self.set_header("Content-Type", "text/plain")
        arduino = self.settings.arduino
        arduino.iterate()
        self.write(str(int(arduino.digital[_num(name)].read())))

    def put(self, name):
        t1 = time.time()
        self.settings.arduino.digital[_num(name)].write(int(self.request.body))
        log.debug("arduino write in %.1f ms" % (1000 * (time.time() - t1)))
        

class pinMode(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self, name):
        self.set_header("Content-Type", "text/plain")
        mode = self.settings.arduino.digital[_num(name)].get_mode()
        self.write({pyduino.DIGITAL_INPUT : "input",
                    pyduino.DIGITAL_OUTPUT : "output"}[mode])
    
    def put(self, name):
        mode = {
            "input" : pyduino.DIGITAL_INPUT,
            "output" : pyduino.DIGITAL_OUTPUT}[self.request.body.strip()]
        self.settings.arduino.digital[_num(name)].set_mode(mode)

class Pid(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain")
        self.write(str(os.getpid()))

class index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        """
        this is a suitable status check; it does a round-trip to arduino
        """
        # this would be a good ping() call for pyduino
        self.settings.arduino.sp.write(chr(pyduino.REPORT_VERSION))
        self.settings.arduino.iterate()
        
        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(open('index.html').read())
    
class Application(cyclone.web.Application):
    def __init__(self, arduino):
        handlers = [
            (r"/", index),
            (r'/pin/(.*)/mode', pinMode),
            (r'/pin/(.*)', pin),
            (r'/pid', Pid),
            # web refresh could benefit a lot from a json resource that
            # gives all the state
        ]
        settings = {"arduino" : arduino,}
        cyclone.web.Application.__init__(self, handlers, **settings)

class WatchPins(object):
    def __init__(self, arduino, conf):
        self.arduino, self.conf = arduino, conf
        self.lastState = {}
        self.pins = conf['watchPins']
        if self.pins == 'allInput':
            self.watchAllInputs()
        for pin in self.pins:
            arduino.digital_ports[pin >> 3].set_active(1)
            arduino.digital[pin].set_mode(pyduino.DIGITAL_INPUT)

    def watchAllInputs(self):
        raise NotImplementedError("this needs to be updated whenever the modes change")
        self.pins = [p for p in range(2, 13+1) if
                     self.arduino.digital[p].get_mode() ==
                     pyduino.DIGITAL_INPUT]

    def reportPostError(self, fail, pin, value, url):
        log.error("failed to send pin %s update (now %s) to %r: %r" % (pin, value, url, fail)) 
        
    def poll(self):
        try:
            self._poll()
        except Exception, e:
            log.error("during poll:", exc_info=1)

    def _poll(self):
        # this can IndexError for a port number being out of
        # range. I'm not sure how- maybe error data coming in the
        # port?
        arduino.iterate()
        for pin in self.pins:
            current = arduino.digital[pin].read()
            if current != self.lastState.get(pin, None):
                d = getPage(
                    self.conf['post'],
                    method="POST",
                    postdata=simplejson.dumps(dict(board=self.conf['boardName'], pin=pin, level=int(current))),
                    headers={'Content-Type' : 'application/json'})
                d.addErrback(self.reportPostError, pin, current, self.conf['post'])

                self.lastState[pin] = current

if __name__ == '__main__':

    config = { # to be read from a file
        'arduinoPort': '/dev/ttyUSB0',
        'servePort' : 9056,
        'pollFrequency' : 20,
        'post' : 'http://bang:9069/pinChange',
        'boardName' : 'theater', # gets sent with updates
        'watchPins' : [9, 10], # or 'allInput' (not yet working)
        # todo: need options to preset inputs/outputs at startup
        }

    arduino = pyduino.Arduino(config['arduinoPort'])
    wp = WatchPins(arduino, config)
    task.LoopingCall(wp.poll).start(1/config['pollFrequency'])
    reactor.listenTCP(config['servePort'], Application(arduino))
    reactor.run()
