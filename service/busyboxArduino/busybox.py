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

sendOneShot((ROOM['greets'],
             ROOM['change'],
             ROOM['down']))

bb = Busybox()
words = open('/usr/share/dict/words').readlines()

lastWordTime = 0
last = None
s1 = []

def poll():
    global lastWordTime, s1, last
    now = time.time()
    if now - lastWordTime > 1:
        msg = '%15s' % random.choice(words).strip()[:15]
        bb.writeMessage(1, 1, msg)
        lastWordTime = now
    last = bb.poll()
    if 'slider1' in last:
        s1 = s1[-5:] + [last['slider1']]
        if len(s1) > 4:
            median = sorted(s1)[2]
            bb.setBacklight(min(255, median // 4))
    if 'keyDown' in last:
        keyNum = last['keyDown']
        sendOneShot((ROOM['ariBed/button%s' % keyNum],
                     ROOM['change'],
                     ROOM['down']))


@klein.route('/graph', methods=['GET'])
def getGraph(request):
    g = StateGraph(ROOM.busybox)
    g.add((ROOM.busybox, ROOM.localHour, Literal('x')))
    for attr in ['slider1', 'slider2', 'slider3', 'slider4']:
        # needs: smoothing, exp curve correction
        g.add((ROOM['busybox/%s' % attr], ROOM.value, Literal(round(last[attr] / 1021, 3))))
    request.setHeader('Content-type', 'application/x-trig')
    return g.asTrig()

task.LoopingCall(poll).start(.05)
        
klein.run('0.0.0.0', port=9056)

