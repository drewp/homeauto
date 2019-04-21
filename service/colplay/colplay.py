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
from influxdb import InfluxDBClient
from rdflib import Namespace, Graph
from rdflib.parser import StringInputSource

ROOM = Namespace('http://projects.bigasterisk.com/room/')

influx = InfluxDBClient('bang', 9060, 'root', 'root', 'main')

def currentAudio(location='frontbed'):
    t = time.time()
    row = list(influx.query("""SELECT mean(value) FROM audioLevel WHERE "location" = '%s' AND time > %ds""" % (location, t - 30)))[0][0]
    log.debug("query took %.03fms", 1000 * (time.time() - t))
    base = {'frontbed': .015,
            'living': .03,
    }[location]
    high = {
        'frontbed': .40,
        'living': .3,
        }[location]
    return max(0.0, min(1.0, (row['mean'] - base) / high))


logging.basicConfig(level=logging.INFO)
log = logging.getLogger()
logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.WARN)

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

theaterUrl = 'http://10.1.0.1:9059/output?p=http://projects.bigasterisk.com/room/color&s=http://bigasterisk.com/homeauto/board0/'
        
lightResource = {
    'theater_left_top_0': theaterUrl + 'rgb_left_top_0',
    'theater_left_top_1': theaterUrl + 'rgb_left_top_1',
    'theater_left_top_2': theaterUrl + 'rgb_left_top_2',
    'theater_right_top_2': theaterUrl + 'rgb_right_top_2',
    'theater_right_top_1': theaterUrl + 'rgb_right_top_1',
    'theater_right_top_0': theaterUrl + 'rgb_right_top_0',
    'theater_left_bottom_0': theaterUrl + 'rgb_left_bottom_0',
    'theater_left_bottom_1': theaterUrl + 'rgb_left_bottom_1',
    'theater_left_bottom_2': theaterUrl + 'rgb_left_bottom_2',
    'theater_right_bottom_2': theaterUrl + 'rgb_right_bottom_2',
    'theater_right_bottom_1': theaterUrl + 'rgb_right_bottom_1',
    'theater_right_bottom_0': theaterUrl + 'rgb_right_bottom_0',
    }

lightYPos = {
    'theater_left_top_0': 130,
    'theater_left_top_1': 132,
    'theater_left_top_2': 134,
    'theater_right_top_2': 135,
    'theater_right_top_1': 137,
    'theater_right_top_0': 139,
    'theater_left_bottom_0': 153,
    'theater_left_bottom_1': 156,
    'theater_left_bottom_2': 159,
    'theater_right_bottom_2': 162,
    'theater_right_bottom_1': 165,
    'theater_right_bottom_0': 168,
}

def hexFromRgb(rgb):
    return rgb_to_hex(tuple([x // 4 for x in rgb])).encode('ascii')

def setColor(lightName, rgb):
    """takes 10-bit r,g,b

    returns even if the server is down
    """
    log.debug("setColor(%r,%r)", lightName, rgb)
  
    serv = lightResource[lightName]

    h = hexFromRgb(rgb)
    log.debug("put %r to %r", h, serv)
    t1 = time.time()
    d = fetch(url=serv, method='PUT', postdata=h,
              headers={'content-type': ['text/plain']})

    def err(e):
        log.warn("http client error on %s: %s" % (serv, e))
        raise e
    d.addErrback(err)


    def done(ret):
        log.debug('put took %.1fms', 1000 * (time.time() - t1))
    d.addCallback(done)
    return d


pxPerHour = 100
    
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
            x = int(((hr - 12) % 24) * pxPerHour) % 2400
            log.debug("x = %s", x)

            audioLevel = currentAudio('frontbed')
            log.debug('level = %s', audioLevel)
            for i, (name, ypos) in enumerate(sorted(lightYPos.items())):

                if i / len(lightYPos) < audioLevel:
                    setColor(name, (500, 0, 0))
                else:
                    setColor(name, (0, 0, 0))
                continue
                
                if now > self.autosetAfter[name]:
                    c = self.img.getColor(x, ypos)
                    d = setColor(name, c)
            self.lastUpdateTime = time.time()
        except Exception:
            self.lastError = traceback.format_exc()
            log.error(self.lastError)
            self.lastErrorTime = time.time()
            

            
class OneShot(cyclone.web.RequestHandler):
    def post(self):
        g = Graph()
        g.parse(StringInputSource(self.request.body), format={
            'text/n3': 'n3',
        }[self.request.headers['content-type']])

        for anim in g.subjects(ROOM['playback'], ROOM['start']):
            startAnim(anim)
            
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
task.LoopingCall(lightState.step).start(3)#3600 / pxPerHour)
log.info("listening http on 9051")
reactor.listenTCP(9051, cyclone.web.Application([
    (r'/', IndexHandler),
    (r'/oneShot', OneShot),
    ], lightState=lightState))
reactor.run()
