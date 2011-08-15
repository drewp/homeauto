#!/usr/bin/python
"""
normal accessing of the 'temperature' field on the sensors wasn't
working. I always got '85' (the power-on reset value). owfs verison is 2.7p2

http://sourceforge.net/mailarchive/forum.php?thread_name=fba87cb90612051724o705bfed0ub780325b915ed541%40mail.gmail.com&forum_name=owfs-developers

Asking for simultaneous read seems to work, and I'm fine with doing that.

the stock modules for onewire are bad; they will take all your CPU. to
turn them off, see:
http://tomasz.korwel.net/2006/07/02/owfs-instalation-on-ubuntu-606/#comment-12246

For the python 'ow' package, get
http://downloads.sourceforge.net/owfs/owfs-2.7p7.tar.gz?modtime=1222687523&big_mirror=0
or similar. Install the libusb-dev and swig packages first for usb and
python support.

2009-02-21 i'm now on ow.__version__ = '2.7p16-1.15'
./configure --disable-owtcl --disable-owperl --disable-owphp --disable-ha7 --disable-ownet --disable-ownetlib --disable-owserver --disable-parport

2011-02-26 now on 2.8p6

how to run their server:
bang(pts/6):/my/dl/lib/owfs-2.8p6/module/owserver/src/c% sudo ./owserver -u -p 9999 --foreground --error_level 9 --error_print 2

owshell/src/c/owget -s 9999 /uncached/10.52790F020800/temperature /uncached/10.4F718D000800/temperature /uncached/10.9AA2BE000800/temperature


but the previous 2.7 version was getting 2/3 measurements, while 2.8
was getting 1/3 measurements!

"""
from __future__ import division
import time, logging, traceback, sys, cyclone.web, jsonlib, restkit
from twisted.internet.task import LoopingCall, deferLater
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor
import ow

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

sys.path.append("/my/proj/room")
from carbondata import CarbonClient

class TempReader(object):
    def __init__(self):
        self.expectedSensors = 3
        self.ow = None
        self.initOnewire()
        self.firstSensorLoop = True

    def initOnewire(self):
        """open usb connection and configure ow lib. Run this again if
        things get corrupt"""
        ow.init('u')
        # this might PRINT a 'Could not open the USB adapter.' message, but I
        # don't know how to trap it

    @inlineCallbacks
    def getCompleteTemps(self, maxTime=120):
        ret = {}
        tries = 0
        now = time.time()
        giveUp = now + maxTime

        self.requestTemps()
        sensors = set(self.allSensors())
        
        while now < giveUp:
            tries += 1
            ret.update(self.getTemps(sensors - set(ret.keys())))

            if len(ret) >= self.expectedSensors:
                log.info("after %s tries, temps=%s" % (tries, ret))
                break

            log.debug("..only have %s measurements; still trying for %d secs" %
                      (len(ret), giveUp - now))
            self.initOnewire()
            self.requestTemps()
            yield deferLater(reactor, .5, lambda: None)
            now = time.time()
        else:
            log.info("giving up after %s secs, only got %s measurements" %
                     (maxTime, len(ret)))
        returnValue(dict([(s.address,val) for s, val in ret.items()]))

    def allSensors(self):
        return ow.Sensor('/').sensors()

    def requestTemps(self):
        ow.owfs_put('/uncached/simultaneous/temperature', '1')

    def getTemps(self, sensors):
        ret = {}
        try:
            for sens in sensors:
                if self.firstSensorLoop:
                    log.debug("found sensor address %r, type=%r" %
                              (sens.address, sens.type))
                if sens.type != 'DS18S20':
                    continue
                try:
                    t = sens.temperature.strip()
                    if t == '85':
                        log.debug(
                            "  sensor %s says 85 (C), power-on reset value" %
                            sens.address)
                        continue
                    tFar = float(t) * 9/5 + 32
                    log.debug("  %s reports temp %r F" % (sens.address, tFar))
                except ow.exUnknownSensor, e:
                    log.warn(e)
                    continue
                ret[sens] = tFar
        except KeyboardInterrupt: raise
        except Exception, e:
            traceback.print_exc()
        self.firstSensorLoop = False
        return ret
    

class Poller(object):
    def __init__(self):
        self.reader = TempReader()
        self.lastPollTime = 0
        self.lastDoc = []
        self.carbon = CarbonClient(serverHost='bang')

    def getHttpTemps(self):
        ret = {}
        
        for url, name in [("http://star:9014/", "ariroom"),
                          ("http://space:9080/", "frontDoor"),
                          ]:
            for tries in range(3):
                try:
                    res = restkit.Resource(url, timeout=5)
                    temp = jsonlib.read(res.get("temperature").body_string(), 
                                        use_float=True)['temp']
                    log.debug("got http temp %s = %r", name, temp)
                    ret[name] = temp
                    break
                except Exception, e:
                    log.warn(e)
        return ret

    @inlineCallbacks
    def sendTemps(self):
        try:
            temps = yield self.reader.getCompleteTemps(maxTime=30)
        except Exception, e:
            reactor.stop()
            raise
        temps.update(self.getHttpTemps())
        now = time.time()
        rows = []
        for k, v in temps.items():
            row = 'system.house.temp.%s' % {
                '104F718D00080038': 'downstairs' ,
                '109AA2BE000800C7': 'livingRoom',
                '1052790F02080086' : 'bedroom',
                '1014958D0008002B': 'unused1', # when you set this, fix expectedSensors count too
                '10CB6CBE0008005E': 'bedroom-broken',
                }.get(str(k), str(k)), float(v)
            self.carbon.send(row[0], row[1], now)
            rows.append(row)

        self.lastPollTime = now
        self.lastDoc = rows

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):

        dt = time.time() - self.settings.poller.lastPollTime
        if dt > 120 + 50:
            raise ValueError("last poll %s sec ago" % dt)
        
        self.set_header("Content-Type", "text/plain")
        self.write("onewire reader (also gathers temps from arduinos); logs to graphite.\n\n Last temps: %r" % self.settings.poller.lastDoc)

if __name__ == '__main__':
    log.setLevel(logging.INFO)
    poller = Poller()
    poller.sendTemps()
    reactor.listenTCP(9078, cyclone.web.Application([
        (r'/', Index),
        ], poller=poller))

    LoopingCall(poller.sendTemps).start(interval=120)
    reactor.run()
