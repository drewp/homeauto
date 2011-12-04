#!/usr/bin/python

import struct, time, sys, logging, traceback, os, cyclone.web
from serial import Serial, SerialException
from twisted.internet.task import LoopingCall
from twisted.internet import reactor

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

sys.path.append("/my/proj/room")
from carbondata import CarbonClient

class Command(object):
    getVersion = 0x01
    getPowerNow = 0x10

class Sleeping(ValueError):
    """haven't checked the spec, but this is what I get when the
    inverter is off at night"""
    
class Comm(object):
    def __init__(self, device):
        self.ser = Serial(device, baudrate=19200)

    def request(self, device, number, command):
        self.writeMsg(device, number, command, data="\x01")
        return self.readMsg()

    def requestNumeric(self, device, number, command):
        buf = self.request(device, number, command)
        if len(buf) != 3:
            if buf == '\x10\x05':
                raise Sleeping()
            raise ValueError("Expected 3 bytes for command %r, not %r" %
                             (command, buf))
        msb, lsb, exp = struct.unpack("!BBb", buf)
        return ((msb << 8) + lsb) * 10**exp
        
    def writeMsg(self, device, number, command, data=""):
        length = len(data)
        commandVal = getattr(Command, command)
        checksum = sum(x for x in [length, device, number, commandVal] +
                       [ord(x) for x in data]) & 0xff
        args = 0x80, 0x80, 0x80, length, device, number, commandVal, data, checksum
        log.debug("Sending: %s %r", command, args)
        self.ser.write(struct.pack("!BBBBBBBsB", *args))


    def readMsg(self):
        log.debug("Read header..")
        (s1, s2, s3, length, device, number, command) = struct.unpack(
            "!BBBBBBB", self.ser.read(7))
        if not s1 == s2 == s3 == 0x80:
            raise ValueError("incorrect header in response: %r" % vars())
        log.debug("Read %d bytes of data", length)
        data = self.ser.read(length)
        cksum = self.ser.read(1)
        log.debug("  -> %r", data)
        return data

class Poller(object):
    def __init__(self, carbon):
        self.carbon = carbon
        self.lastPollTime = 0
        self.reset()
        LoopingCall(self.poll).start(interval=10)

    def reset(self):
        log.info("reopening serial port")
        for port in ['/dev/serial/by-id/usb-0557_2008-if00-port0']:
            try:
                self.comm = Comm(port)
                break
            except SerialException, e:
                pass
        else:
            # among other things, a serial exception for too many open files 
            log.error(e)
            os.abort()
        log.info("version: %r", self.comm.request(device=1, number=0,
                                                  command="getVersion"))

    def poll(self):
        try:
            watts = self.comm.requestNumeric(device=1, number=0,
                                             command="getPowerNow")
            self.carbon.send('system.house.solar.power_w', watts)
        except Sleeping:
            log.debug("sleeping")
        except ValueError:
            log.error(traceback.format_exc())
            self.reset()
        except Exception:
            traceback.print_exc()
            os.abort()
        self.lastPollTime = time.time()


class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        age = time.time() - self.settings.poller.lastPollTime
        if age > 12:
            raise ValueError("poll data is stale. age=%s" % age)
        
        self.write("powerInverter reading from serial port and writing to graphite")

log.setLevel(logging.INFO)
carbon = CarbonClient(serverHost='bang')
p = Poller(carbon)
reactor.listenTCP(9078, cyclone.web.Application([
    (r'/', Index),
    ], poller=p))
reactor.run()
