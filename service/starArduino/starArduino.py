"""
arduino driver for the nightlight+buttons+temp setup running on star

"""
from __future__ import division

import sys,json
from twisted.internet import reactor, task
from twisted.internet.task import LoopingCall
import cyclone.web, restkit

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
        self.write(json.dumps({"temp" : f}))

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
    
class Barcode(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain")
        ser = self.settings.arduino.ser
        ser.write("\x60\x02")
        self.write(str(ser.readJson()))

class BarcodeBeep(PrettyErrorHandler, cyclone.web.RequestHandler):
    def put(self):
        self.set_header("Content-Type", "text/plain")
        ser = self.settings.arduino.ser
        ser.write("\x60\x03")
        self.write(str(ser.readJson()))

def barcodeWatch(arduino, postBarcode):
    arduino.ser.write("\xff\xfb")
    ret = arduino.readJson()
    if not ret['barcode']:
        return
    if ret['barcode'] == "27 80 48 13 ":
        return # scanner's beep response

    arduino.ser.write("\xff\xfc")
    arduino.readJson() # my beep response
    s = ''.join(chr(int(x)) for x in ret['barcode'].split())
    for code in s.split('\x02'):
        if not code:
            continue
        if not code.endswith('\x03'):
            print "couldn't read %r" % code
            return
        codeType = {'A':'UPC-A',
                    'B':'JAN-8',
                    'E':'UPC-E',
                    'N':'NW-7',
                    'C':'CODE39',
                    'I':'ITF',
                    'K':'CODE128',
                    }[code[0]]
        code = code[1:-1]
        try:
            postBarcode.post(payload=json.dumps(
                {'barcodeType':codeType, 'code':code}),
                             headers={"content-type" :
                                      "application/json"})
        except Exception, e:
            print "post err", e

    
class Graph(PrettyErrorHandler, cyclone.web.RequestHandler):    
    def get(self):
        raise NotImplementedError
    
if __name__ == '__main__':
    class A(ShiftbriteArduino):
        # from loggingserial.py
        def readJson(self):
            line = ''
            while True:
                c = self.ser.read(1)
                #print "gotchar", repr(c)
                if c:
                    line += c
                    if c == "\n":
                        break
                else:
                    raise ValueError("timed out waiting for chars")
            return json.loads(line)

    sb = A(numChannels=3)

    colors = [(0,0,0)] * sb.numChannels

    aw = ArduinoWatcher(sb)
    task.LoopingCall(aw.poll).start(1.0/20)

    postBarcode = restkit.Resource('http://star:9011/barcodeScan')
    task.LoopingCall(barcodeWatch, sb, postBarcode).start(interval=.5)
    
    reactor.listenTCP(9014, cyclone.web.Application([
        (r'/', Index),
        (r'/temperature', Temperature),
        (r'/brite/(\d+)', Brite),
        (r'/barcode', Barcode),
        (r'/barcode/beep', BarcodeBeep),
        (r'/graph', Graph),
        ], arduino=sb, colors=colors))
    reactor.run()
