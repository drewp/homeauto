from __future__ import division
"""
drives the heater output pin according to a requested temperature that you can edit. The temp is stored in mongodb.
"""
import cyclone.web, sys, urllib, time, pymongo, json, datetime
from dateutil.tz import tzlocal
from cyclone.httpclient import fetch
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

db = pymongo.Connection("bang")['thermostat']

@inlineCallbacks
def http(method, url, body=None):
    resp = (yield fetch(url, method=method, postdata=body,
                        headers={'user-agent': ['thermostat']}))
    if resp.code != 200:
        raise ValueError("%s returned %s: %s" % (url, resp.code, resp.body))
    returnValue(resp.body)

class Unknown(object):
    pass
    
class Therm(object):
    def __init__(self):
        self._lastOn = Unknown
        self._lastOff = time.time() - 1000

        # the non-logging path
        self.graphite = 'http://bang:9037/render' 
        
        # get this from devices.n3
        self.heaterPin = 'http://bang:9056/pin/d4'

    def getRequest(self):
        return (db['request'].find_one(sort=[('t', -1)]) or
                {'tempF':60}
               )['tempF']
    
    def setRequest(self, f):
        db['request'].insert({'tempF': f, 't':datetime.datetime.now(tzlocal())})
        self.step()
        
    @inlineCallbacks
    def step(self):
        roomF = yield self.getRoomTempF()
        requestedF = self.getRequest()
        active = yield self.active()
        minsOff = self.minutesSinceOff()
        minsOn = self.minutesSinceOn()

        log.info("roomF=%(roomF)s requestedF=%(requestedF)s active=%(active)s "
                 "minsOn=%(minsOn)s minsOff=%(minsOff)s" % vars())
        if not active:
            if roomF < requestedF - 1:
                if minsOff > 5:
                    log.info("start heater")
                    self.startCycle()
                else:
                    log.info("wait to start")
            else:
                pass
        else:
            if roomF > requestedF + 1:
                log.info("stop heater")
                self.stopCycle()
            elif minsOn > 50:
                log.info("heater on too long- stopping")
                self.stopCycle()
            else:
                log.info("ok to keep warming")

    @inlineCallbacks
    def getRoomTempF(self):
        target = 'system.house.temp.livingRoom'
        body = (yield http('GET', self.graphite + '?' +
                           urllib.urlencode({
                               'target':"keepLastValue(%s)" % target,
                               'rawData':'true',
                               'from':'-60minutes',
                           })))
        latest = float(body.split(',')[-1])
        returnValue(latest)

    @inlineCallbacks
    def active(self):
        ret = yield http('GET', self.heaterPin)
        returnValue(bool(int(ret.strip())))

    @inlineCallbacks
    def stopCycle(self):
        log.info("heater off")
        # need to make it be an output!
        yield http('PUT', self.heaterPin, body='0')
        self._lastOff = time.time()

    @inlineCallbacks
    def startCycle(self):
        log.info("heater on")
        yield http('PUT', self.heaterPin, body='1')
        self._lastOn = time.time()
        
    def minutesSinceOff(self):
        if self._lastOff is Unknown:
            self._lastOff = time.time()
            return 0
        return (time.time() - self._lastOff) / 60

    def minutesSinceOn(self):
        if self._lastOn is Unknown:
            self._lastOn = time.time()
            return 0
        return (time.time() - self._lastOn) / 60
        

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.write("thermostat. requested temp is %s." %
                   self.settings.therm.getRequest())

class RequestedTemperature(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.write(json.dumps({"tempF" : self.settings.therm.getRequest()}))
    def put(self):
        f = json.loads(self.request.body)['tempF']
        if not isinstance(f, (int, float)):
            raise TypeError("tempF was %r" % f)
        self.settings.therm.setRequest(f)
        self.write("ok")
        
if __name__ == '__main__':
    t = Therm()
    def step():
        try:
            t.step()
        except Exception, e:
            log.warn(e)
            
    LoopingCall(step).start(interval=30)
    
    reactor.listenTCP(10001, cyclone.web.Application([
        (r'/', Index),
        (r'/requestedTemperature', RequestedTemperature),
        ], therm=t))
    
    reactor.run()
