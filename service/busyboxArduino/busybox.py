from __future__ import division
import serial, struct, json, sys

from rdflib import Namespace, Literal
sys.path.append("/my/site/magma")
from stategraph import StateGraph
import klein
from twisted.internet import task
import random, time

import restkit
reasoning = restkit.Resource("http://bang:9071/", timeout=1)
ROOM = Namespace("http://projects.bigasterisk.com/room/")

def sendOneShot(stmt):
    try:
        t1 = time.time()
        print "post to reasoning", stmt
        p = reasoning.post("oneShot",
                           headers={"content-type": "text/n3"},
                           payload=("%s %s %s ." %
                                    tuple(n.n3() for n in stmt)))
    except restkit.errors.RequestFailed:
        print "oneShot failed"
        return
    print "posted in %.04f sec. %r" % (time.time() - t1,
                                       p.body_string())
    

class Busybox(object):
    def __init__(self, port='/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A4001lVK-if00-port0'):
        self.serial = serial.Serial(port, baudrate=115200, timeout=.2)

    def poll(self):
        for tries in range(5):
            self.serial.write('\x60\x00')
            line = self.serial.readline()
            if not line.startswith('{'):
                continue
            if tries > 0:
                print "after %s tries" % tries
            return json.loads(line)
        return {'error': 'invalid response'}
        
    def writeMessage(self, row, col, text):
        msg = struct.pack('BBBBB', 0x60, 0x01, row, col, len(text)) + text
        self.serial.write(msg)

    def setBacklight(self, level):
        self.serial.write(struct.pack('BBB', 0x60, 0x02, level))

    def sendIr(self, remote, command):
        code = {
            'led_22_key': {
                # LED618 remote command byte (addr is ff)
                # see https://github.com/alistairallan/RgbIrLed/blob/master/RgbIrLed.cpp#L44
                'ON': 0xE0,
                'OFF': 0x60,
                'BRIGHTNESS_UP': 0xA0,
                'BRIGHTNESS_DOWN': 0x20,
                'FLASH': 0xF0,
                'STROBE': 0xE8,
                'FADE': 0xD8,
                'SMOOTH': 0xC8,
                'RED': 0x90, 'GREEN': 0x10, 'BLUE': 0x50, 'WHITE': 0xD0,
                'ORANGE': 0xB0, 'YELLOW_DARK': 0xA8, 'YELLOW_MEDIUM': 0x98, 'YELLOW_LIGHT': 0x88,
                'GREEN_LIGHT': 0x30, 'GREEN_BLUE1': 0x28, 'GREEN_BLUE2': 0x18, 'GREEN_BLUE3': 0x08,
                'BLUE_RED': 0x70, 'PURPLE_DARK': 0x68, 'PURPLE_LIGHT': 0x58, 'PINK': 0x48,
            },
            'led_44_key': {
                # 44 key remote. command chart: http://blog.allgaiershops.com/2012/05/
                'up': 0x3A, 'down': 0xBA, 'play': 0x82, 'power': 0x02, 
                'red0': 0x1A, 'grn0': 0x9A, 'blu0': 0xA2, 'wht0': 0x22, 
                'red1': 0x2A, 'grn1': 0xAA, 'blu1': 0x92, 'wht1': 0x12, 
                'red2': 0x0A, 'grn2': 0x8A, 'blu2': 0xB2, 'wht2': 0x32, 
                'red3': 0x38, 'grn3': 0xB8, 'blu3': 0x78, 'wht3': 0xF8, 
                'red4': 0x18, 'grn4': 0x98, 'blu4': 0x58, 'wht4': 0xD8, 
                'RUp': 0x28, 'GUp': 0xA8, 'BUp': 0x68, 
                'RDn': 0x08, 'GDn': 0x88, 'BDn': 0x48, 
                'Quick': 0xE8, 'Slow': 0xC8, 
                'DIY1': 0x30, 'DIY2': 0xB0, 'DIY3': 0x70, 'DIY4': 0x10, 'DIY5': 0x90, 'DIY6': 0x50, 
                'AUTO': 0xF0, 
                'Flash': 0xD0, 
                'JMP3': 0x20, 'JMP7': 0xA0, 
                'Fade': 0x60, 'Fade7': 0xE0,
            }
        }

        address = {
            'led_22_key': 0x00,
            'led_44_key': 0x00,
        }[remote]
        self.serial.write(struct.pack('BBBB', 0x60, 0x03, address, code[remote][command]))
        time.sleep(.2)
        

bb = Busybox()
words = open('/usr/share/dict/words').readlines()

while 1:
    bb.sendIr('led_22_key', 'RED')
    bb.sendIr('led_22_key', 'BRIGHTNESS_DOWN')
    bb.sendIr('led_22_key', 'BRIGHTNESS_DOWN')
    bb.sendIr('led_22_key', 'BRIGHTNESS_DOWN')
    bb.sendIr('led_22_key', 'BLUE')
    bb.sendIr('led_22_key', 'BRIGHTNESS_DOWN')
    bb.sendIr('led_22_key', 'BRIGHTNESS_DOWN')
    bb.sendIr('led_22_key', 'BRIGHTNESS_DOWN')



class Poller(object):
    def __init__(self):
        self.lastWordTime = 0
        self.last = None
        self.s1 = []

    def poll(self):
        try:
            self.tryPoll()
        except Exception as e:
            print "poll failed: %r" % e
            
    def tryPoll(self):
        now = time.time()
        if now - self.lastWordTime > 1:
            msg = '%15s' % random.choice(words).strip()[:15]
            bb.writeMessage(1, 1, msg)
            self.lastWordTime = now
        self.last = bb.poll()
        print self.last
        if 'slider1' in self.last:
            self.s1 = self.s1[-5:] + [self.last['slider1']]
            if len(self.s1) > 4:
                median = sorted(self.s1)[2]
                bb.setBacklight(min(255, median // 4))
        if 'keyDown' in self.last:
            keyNum = self.last['keyDown']
            sendOneShot((ROOM['ariBed/button%s' % keyNum],
                         ROOM['change'],
                         ROOM['down']))
        if self.last['motion']:
            bb.sendIr('led_22_key', 'ON')
        else:
            bb.sendIr('led_22_key', 'OFF')


@klein.route('/graph', methods=['GET'])
def getGraph(request):
    g = StateGraph(ROOM.busybox)
    g.add((ROOM.busybox, ROOM.localHour, Literal('x')))
    for attr in ['slider1', 'slider2', 'slider3', 'slider4']:
        # needs: smoothing, exp curve correction
        g.add((ROOM['busybox/%s' % attr], ROOM.value, Literal(round(poller.last[attr] / 1021, 3))))
    g.add((ROOM['busybox/motion'], ROOM.value, Literal(poller.last['motion'])))
    request.setHeader('Content-type', 'application/x-trig')
    return g.asTrig()

poller = Poller()
task.LoopingCall(poller.poll).start(.05)

# todo: watch reasoning graph. put lines on display. send updated ir codes.

klein.run('0.0.0.0', port=9056)

