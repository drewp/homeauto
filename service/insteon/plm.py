import serial, struct, time, inspect, bottle


class InsteonModem(object):
    """
    spec at http://www.aartech.ca/docs/2412sdevguide.pdf
    and http://www.insteon.net/pdf/insteonwtpaper.pdf

    https://github.com/zonyl/pytomation/blob/master/pytomation/interfaces/insteon.py is very similar
    
    """
    def __init__(self):
        self.port = serial.Serial(port='/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A900ex7S-if00-port0', baudrate=19200, timeout=2)
        self.port.flushInput()
        
    def _send(self, cmd, nBytesReturned=0, tries=3):
        """cmd is without the 0x02; the result does not include the
        command echo nor the ACK byte at the end"""
        try:
            msgOut = "\x02"+cmd
            
            caller = inspect.currentframe()
            while caller.f_code.co_name.startswith('_'):
                caller = caller.f_back
            caller = caller.f_code.co_name
            print "sending %s bytes (from %r): %r" % (len(msgOut), caller, msgOut)
            self.port.write(msgOut)
            expected = 1+len(cmd) + nBytesReturned + 1
            print "expecting %s bytes" % expected
            raw = self.port.read(expected)
            if len(raw) < expected:
                raise ValueError("short read: %r" % raw)

            if raw[-1] == '\x15':
                raise ValueError("NAK error from insteon: %r" % raw)
            if raw[-1] != '\x06':
                raise ValueError("received value %r didn't end with 0x06" % raw)

            print repr(raw)
            return raw[1+len(cmd):-1]
        except ValueError, e:
            if tries > 0:
                print "retrying for", e
                time.sleep(2)
                self._send(cmd, nBytesReturned, tries-1)
            raise


    def _sendInsteonStandard(self, toAddress, cmd1, cmd2, data="",
                             broadcast=0, group=0, ack=0):
        if len(data) == 0:
            extended = 0
        elif len(data) == 14:
            extended = 1
        else:
            raise NotImplementedError("data must be 6 or 14 bytes")
        flags = chr(0x80 * broadcast +
                    0x40 * group +
                    0x20 * ack +
                    0x10 * extended +
                    0x0f)

        return self._send("\x62" + toAddress + flags + cmd1 + cmd2 + data)

    def getImInfo(self):
        msg = map(ord, self._send("\x60", 6))
        return {'id' : "%02X%02X%02X" % (msg[0], msg[1], msg[2]),
                'deviceCategory' : msg[3],
                'deviceSubcategory' : msg[4],
                'firmwareRevision': msg[5]}

    def setConfiguration(self, disableAutomaticLinking=0,
                         monitorMode=0,
                         disableAutomaticLed=0,
                         disableDeadman=0):
        self._send("\x6b" + chr(0x80 * disableAutomaticLinking +
                                0x40 * monitorMode +
                                0x20 * disableAutomaticLed +
                                0x10 * disableDeadman))

    def getConfiguration(self):
        c = ord(self._send("\x73", 3)[0])
        return {'disableAutomaticLinking': bool(c & 0x80),
                'monitorMode': bool(c & 0x40),
                'disableAutomaticLed': bool(c & 0x20),
                'disableDeadman': bool(c & 0x10),
                }

    def setLed(self, on):
        """needs setConfiguration(disableAutomaticLed=1) first"""
        self._send("\x6d" if on else "\x6e")

    def enterLinkMode(self, group):
        return self._sendInsteonStandard("\x00\x00\x00", "\x09",
                                         chr(group), broadcast=1)

    def on(self, toAddress, level):
        return self._sendInsteonStandard(toAddress, "\x11", chr(level))

    def beep(self, toAddress, duration):
        return self._sendInsteonStandard(toAddress, "\x30", chr(duration))

    def getDeviceTextString(self, toAddress):
        return self._sendInsteonStandard(toAddress, "\x03", "\x02", "\x00" * 14)

    def setButtonPressed(self):
        """run this then press a real button to setup a link in the
        controller"""
        return self._sendInsteonStandard("\x00\x0a\x0c", "\x01", "\xff", broadcast=1)

    

lamp1 = "\x0f\x6a\xb5"
lamp4 = "\x1a\xce\xa8"
livingRoom1 = "\x0e\xf5\xb7"

#learn livingroom number & how to program it. run setButtonPressed and press livingroom button to enable it. then make web access to the switch. how do we learn switch presses? i have yet to see anything come in. polling call?

im = InsteonModem()
print im.getImInfo()
#print im.getConfiguration()
#im.setConfiguration(disableAutomaticLed=1)
#im.setLed(True)
import time

app = bottle.Bottle()
@app.route('/')
def index():
    return "hello"

@app.route('/output')
def output():
    
    

from gevent.pywsgi import WSGIServer
server = WSGIServer(('', 8002), app)
server.serve_forever()

im.on(lamp4, 255)
1/0

while 1:
    print "lr"
    im.on(livingRoom1, 255)
    time.sleep(1)
    im.on(lamp1, 0)
    time.sleep(3)
    print 'lamp1'
    im.on(livingRoom1, 0)
    time.sleep(1)
    im.on(lamp1, 255)
    time.sleep(3)


#im.setButtonPressed()

#im.enterLinkMode(0)
#print repr(im.getDeviceTextString(lamp1))


while 1:
    print "got %r" % im.port.read()


1/0
im.beep(lamp4, 100)
im.on(lamp4, 255)

#print "status", im._sendInsteonStandard("\x1a\xce\xa8", "\x19", "\x00")
im._sendInsteonStandard("\x1a\xce\xa8", "\x11", "\xff")
print "ping", im._sendInsteonStandard("\x1a\xce\xa8", "\x0f", "\x00")

