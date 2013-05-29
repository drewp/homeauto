#!bin/python
"""
resets usb ports and restarts other services. Must run as root for the usb part.

Other systems that might be able to do conditional tests and commands like this:
  https://github.com/azkaban/azkaban
  nagios
  


run this as root to reset a whole usb device. Ported from
http://marc.info/?l=linux-usb&m=121459435621262&w=2

how to learn what device to reset? lsusb or lsusb -t

how to learn the ioctl number? cpp on this file:

  #include "/usr/include/linux/usbdevice_fs.h"
  #include "/usr/include/asm-generic/ioctl.h"
  USBDEVFS_RESET

last line comes out like this:
(((0U) << (((0 +8)+8)+14)) | ((('U')) << (0 +8)) | (((20)) << 0) | ((0) << ((0 +8)+8)))

this is a py expression:
(((0) << (((0 +8)+8)+14)) | ((ord('U')) << (0 +8)) | (((20)) << 0) | ((0) << ((0 +8)+8)))

----------------

also this other usb reset:

http://davidjb.com/blog/2012/06/restartreset-usb-in-ubuntu-12-04-without-rebooting

"""

from __future__ import division

import cyclone.web, json, traceback, os, sys, time, logging, re
import os, fcntl, commands, socket, logging, time, xmlrpclib, subprocess

from twisted.internet import reactor, task
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred
from twisted.web.client import getPage
sys.path.append("/my/proj/house/frontdoor")
from loggingserial import LoggingSerial        
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

USBDEVFS_RESET = 21780

class Id(object):
    ftdi = "0403:6001"
    frontDoorHub0 = "8087:0024" # bus2 dev 2
    frontDoorHub1 = "0451:2046" # bus2 dev 3
    frontDoorHub2 = "1a40:0101" # bus2 dev 7
    frontDoorHub3 = "0409:0058" # bus2 dev 62
    frontDoorCam = "0ac8:307b"

    bedroomHub0 = "8087:0020"
    bedroomHub1 = "05e3:0608"
    bedroomHub2 = "058f:6254"
    bedroomHub3 = "0409:005a"
    bedroomCam = "046d:08aa"
    bedroomSba = "04d8:000a"
    bedroomArduino = "0403:6001"

    garageHub0 = "1d6b:0002" # bus2 dev1
    garageHub1 = "05e3:0604" # bus2 dev4
    garageArduino = "2341:0001"
    garagePowerSerial = "0557:2008"

    blueHub = "1a40:0101"

hostname = socket.gethostname()

@inlineCallbacks
def getOk(url, timeout=1):
    """can we get a successful status from this url in a short time?"""
    log.debug("testing %s" % url)
    try:
        resp = yield getPage(url, timeout=timeout)
    except Exception, e:
        log.warn("getPage %s", e)
        returnValue(False)

    returnValue(True)

def hubDevice(usbId="1a40:0101"):
    """
    what's the /dev path to the device with this usb id
    """
    for line in commands.getoutput("lsusb").splitlines():
        if 'ID '+usbId in line:
            words = line.split()
            return "/dev/bus/usb/%s/%s" % (words[1], words[3].rstrip(':'))
    raise ValueError("no usb device found with id %r" % usbId)

def haveDevice(usbId):
    try:
        log.debug("checking for %s", usbId)
        dev = hubDevice(usbId)
        # sometimes the dev will exist but fail to open
        open(dev, "r")
        return True
    except (ValueError, IOError):
        return False

def resetDevice(dev):
    """
    send USBDEVFS_RESET to the given /dev address
    """
    d = Deferred()
    log.debug("resetting %s" % dev)
    f=os.open(dev, os.O_WRONLY)
    ret = fcntl.ioctl(f, USBDEVFS_RESET, 0)
    if ret != 0:
        raise ValueError("ioctl failed with %s" % ret)
    reactor.callLater(3, d.callback, None)
    return d

def supervisorRestart(cmds, supervisor="http://localhost:9001"):
    serv = xmlrpclib.ServerProxy(supervisor)
    for c in cmds:
        log.info("restarting %s", c)
        try:
            serv.supervisor.stopProcessGroup(c)
        except xmlrpclib.ResponseError, e:
            log.warn("supervisor.stopProcessGroup error %r, ignoring", e)
        serv.supervisor.startProcess(c)

def resetModules(modules):
    log.info("reloading modules: %s", modules)
    for m in modules:
        subprocess.call(['modprobe', '-r', m])
    for m in modules:
        subprocess.check_call(['modprobe', m])


class Background(object):
    def __init__(self, config, period):
        self.config = config
        self.period = period
        self.lastPollTime = 0

    def assertIsCurrent(self):
        """raise an error if the poll data is not fresh"""
        dt = time.time() - self.lastPollTime
        if dt > self.period * 2:
            raise ValueError("last poll time was too old: %.1f sec ago" % dt)
    
    @inlineCallbacks
    def step(self):
        now = time.time()
        try:
            if hostname == 'bang':
                if (not haveDevice(Id.bedroomCam) or
                    not haveDevice(Id.bedroomArduino)):
                    if haveDevice(Id.bedroomHub3):
                        yield resetDevice(hubDevice(Id.bedroomHub3))
                    else:
                        if haveDevice(Id.bedroomHub2):
                            yield resetDevice(hubDevice(Id.bedroomHub2))
                        else:
                            if haveDevice(Id.bedroomHub1):
                                yield resetDevice(hubDevice(Id.bedroomHub1))
                            else:
                                if haveDevice(Id.bedroomHub0):
                                    yield resetDevice(hubDevice(Id.bedroomHub0))
                                else:
                                    raise ValueError(
                                        "don't even have the first hub")
                    resetModules(['gspca_zc3xx'])
                    supervisorRestart(['webcam_9053'])
                else:
                    log.debug("usb devices look ok")

            elif hostname == 'slash':
                haveFrontHub0 = haveDevice(Id.frontDoorHub0)
                haveFrontHub1 = haveDevice(Id.frontDoorHub1)
                haveFrontHub2 = haveDevice(Id.frontDoorHub2)
                haveFrontHub3 = haveDevice(Id.frontDoorHub3)
                haveGarageHub0 = haveDevice(Id.garageHub0)
                haveGarageHub1 = haveDevice(Id.garageHub1)
                haveFrontDoorCam = haveDevice(Id.frontDoorCam)
                haveV4lDevice = os.path.exists(
                    "/dev/v4l/by-id/usb-Vimicro_Corp._PC_Camera-video-index0")
                haveFrontArduinoServe = (yield getOk('http://slash:9080/'))
                haveFrontWebcamImage = (yield getOk(
                    "http://slash:9023/frontDoor", timeout=10))
                
                log.info(str(vars()))

                if not haveDevice(Id.ftdi):
                    if haveFrontHub3:
                        yield resetDevice(hubDevice(Id.frontDoorHub3))
                    else:
                        if haveFrontHub2:
                            yield resetDevice(hubDevice(Id.frontDoorHub2))
                        else:
                            if haveFrontHub1:
                                yield resetDevice(hubDevice(Id.frontDoorHub1))
                            else:
                                if haveFrontHub0:
                                    yield resetDevice(hubDevice(Id.frontDoorHub0))
                                else:
                                    raise ValueError("don't have the first hub")
                else:
                    log.debug("front door chain looks ok")

                if not haveDevice(Id.garagePowerSerial):
                    if haveGarageHub1:
                        yield resetDevice(hubDevice(Id.garageHub1))
                    else:
                        if haveGarageHub0:
                            yield resetDevice(hubDevice(Id.garageHub0))
                        else:
                            raise ValueError("don't have the first hub")
                else:
                    log.debug("garage chain looks ok")
                    
                if not haveDevice(Id.garageArduino):
                    if haveGarageHub1:
                        yield resetDevice(hubDevice(Id.garageHub1))
                    else:
                        raise ValueError("don't even have the first hub")
                    resetModules(['gspca_zc3xx'])
                    supervisorRestart(['frontDoorArduino_9080'])
                else:
                    if not haveFrontArduinoServe:
                        yield resetDevice(hubDevice(Id.frontDoorHub3))
                        supervisorRestart(['frontDoorArduino_9080'])
                        time.sleep(10)
                    else:
                        log.debug("frontDoorArduino looks ok")

                if not haveFrontWebcamImage:
                    supervisorRestart(['webcam_frontDoor_9023'])
                else:
                    log.debug("front webcam looks ok")

            elif hostname == 'dash':
                if not os.path.exists("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A900gbcG-if00-port0"):
                    yield resetDevice(hubDevice("/dev/bus/usb/003/001"))

            else:
                raise NotImplementedError

            log.debug(" -- finished")
            self.lastPollTime = now

        except Exception, e:
            print "poll error", e
            traceback.print_exc()

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.settings.background.assertIsCurrent()
        
        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(open("index.html").read())

class Devices(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        out = []
        for line in commands.getoutput("lsusb").splitlines():
            words = line.split(None, 6)
            for name, usbId in Id.__dict__.items():
                if usbId == words[5]:
                    break
            else:
                name = "?"
            out.append(dict(dev="/dev/bus/usb/%s/%s" % (words[1], words[3].rstrip(':')),
                            name=name,
                            usbId=words[5],
                            usbName=words[6] if len(words) > 6 else ""))

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({'devices':out}))

class Reset(PrettyErrorHandler, cyclone.web.RequestHandler):
    @inlineCallbacks
    def post(self):
        dev = self.get_argument('dev')
        assert re.match("^[a-z0-9/]+$", dev), dev
        yield resetDevice(dev)
        
        self.set_header("Content-Type", "text/plain")
        self.write("ok")

if __name__ == '__main__':
    config = { # to be read from a file
        'servePort' : 9100,
        'checkPeriod' : 30,
        }

    from twisted.python import log as twlog
    #twlog.startLogging(sys.stdout)

    log.setLevel(logging.DEBUG)

    p = Background(config, config['checkPeriod'])
    task.LoopingCall(p.step).start(config['checkPeriod'])

    reactor.listenTCP(config['servePort'], cyclone.web.Application([
        (r"/", Index),
        (r"/devices", Devices),
        (r"/devices/reset", Reset),
        ], background=p, static_path="static"))
    reactor.run()
