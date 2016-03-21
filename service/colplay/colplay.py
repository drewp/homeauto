"""
Color player: emits many color values that change over time, by
scanning across images and creating new images by blending other
patterns.

Rewrite of pixel/nightlight.py
"""
from __future__ import division
import time, os, logging, json, traceback
from PIL import Image
from datetime import datetime, timedelta
from twisted.internet import reactor, task
import cyclone.web
from dateutil.tz import tzlocal
from cyclone.httpclient import fetch
from webcolors import rgb_to_hex

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()
logging.getLogger('restkit.client').setLevel(logging.WARN)

class Img(object):
    def __init__(self, filename):
        self.filename = filename
        self.reread()

    def reread(self):
        try:
            self.img = Image.open(self.filename)
        except IOError: # probably mid-write
            time.sleep(.5)
            self.img = Image.open(self.filename)
        self.mtime = os.path.getmtime(self.filename)

    def getColor(self, x, y):
        """10-bit rgb"""
        if os.path.getmtime(self.filename) > self.mtime:
            self.reread()
        return [v * 4 for v in self.img.getpixel((x, y))[:3]]
        
lightResource = {
    'theater0': 'http://bang:9059/output?s=http://bigasterisk.com/homeauto/board0/rgb_right_top_2&p=http://projects.bigasterisk.com/room/color',
    }

lightYPos = {
    'theater0' : 135,
}

def hexFromRgb(rgb):
    return rgb_to_hex(tuple([x // 4 for x in rgb])).encode('ascii')

def setColor(lightName, rgb, _req):
    """takes 10-bit r,g,b

    returns even if the server is down
    """
    log.debug("setColor(%r,%r)", lightName, rgb)
  
    serv = lightResource[lightName]
    try:
        h = hexFromRgb(rgb)
        log.debug("put %r to %r", h, serv)
        r = _req(method='PUT', url=serv, body=h,
             headers={"content-type":"text/plain"})
        return r
    except Exception, e:
        log.warn("Talking to: %r" % serv)
        log.warn(e)
        return None

def setColorAsync(lightName, rgb):
    """
    uses twisted http, return deferred or sometimes None when there
    was a warning
    """
    def _req(method, url, body, headers):
        d = fetch(url=url, method=method, postdata=body,
                  headers=dict((k,[v]) for k,v in headers.items()))
        @d.addErrback
        def err(e):
            log.warn("http client error on %s: %s" % (url, e))
            raise e
        return d
    setColor(lightName, rgb, _req=_req)


class LightState(object):
    def __init__(self):
        self.lastUpdateTime = 0
        self.lastErrorTime = 0
        self.lastError = ""
        self.img = Img("pattern.png")
        self.autosetAfter = dict.fromkeys(lightYPos.keys(),
                                          datetime.fromtimestamp(0, tzlocal()))

    def mute(self, name, secs):
        """don't autoset this light for a few seconds"""
        self.autosetAfter[name] = datetime.now(tzlocal()) + timedelta(seconds=secs)

    def step(self):
        try:
            now = datetime.now(tzlocal())
            hr = now.hour + now.minute / 60 + now.second / 3600
            x = int(((hr - 12) % 24) * 50)
            log.debug("x = %s", x)

            for name, ypos in lightYPos.items():
                if now > self.autosetAfter[name]:
                    c = self.img.getColor(x, ypos)
                    setColorAsync(name, c)
            self.lastUpdateTime = time.time()
        except Exception:
            self.lastError = traceback.format_exc()
            self.lastErrorTime = time.time()
            
            
class IndexHandler(cyclone.web.RequestHandler):
    def get(self):
        ls = self.settings.lightState
        now = time.time()
        self.set_header("content-type", "application/json")
        self.set_status(200 if ls.lastUpdateTime > ls.lastErrorTime else 500)
        self.write(json.dumps(dict(
            secsSinceLastUpdate=now - ls.lastUpdateTime,
            secsSinceLastError=now - ls.lastErrorTime,
            lastError=ls.lastError,
            ), indent=4))

lightState = LightState()
task.LoopingCall(lightState.step).start(1)
log.info("listening http on 9051")
reactor.listenTCP(9051, cyclone.web.Application([
    (r'/', IndexHandler),
    ], lightState=lightState))
reactor.run()
