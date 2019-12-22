"""
play sounds according to POST requests.
"""
from docopt import docopt
import cyclone.web
import os, sys, tempfile, itertools
from twisted.internet import reactor
from cyclone.httpclient import fetch
from twisted.web.static import File
from standardservice.logsetup import log, verboseLogging

class LOADING(object): pass

class SoundEffects(object):
    def __init__(self):
        self.buffers = {} # URIRef : path
        self.playingSources = []
        self.queued = []
        self.volume = 1 # level for the next sound that's played (or existing instances of the same sound)

    def _getSound(self, uri):
        def done(resp):
            print('save')
            body = bytes(resp.body)
            path = '/tmp/sound_%s' % hash(uri)
            with open(path, 'wb') as out:
                out.write(body)
            log.info('write %s bytes to %s', len(resp.body), path)
            self.buffers[uri] = path
            print('donesave')

        return fetch(uri.encode('utf8')).addCallback(done).addErrback(log.error)

    def playEffect(self, uri: str):
        if uri not in self.buffers:
            self.buffers[uri] = LOADING
            self._getSound(uri).addCallback(lambda ret: self.playEffect(uri))
            return
        if self.buffers[uri] is LOADING:
            # The first playback loads then plays, but any attempts
            # during that load are dropped, not queued.
            return
        snd = self.buffers[uri]
        print('subp')
        subprocess.check_call(['paplay', snd])
        return

    def done(self, src):
        try:
            self.playingSources.remove(src)
        except ValueError:
            pass

    def stopAll(self):
        while self.playingSources:
            self.playingSources.pop().stop()
        for q in self.queued:
            q.cancel()
        # doesn't cover the callLater ones

class Index(cyclone.web.RequestHandler):
    def get(self):
        self.render('index.html')

class PlaySound(cyclone.web.RequestHandler):
    def post(self):
        uri = self.get_argument('uri')
        self.settings.sfx.playEffect(uri)
        return "ok"

class Volume(cyclone.web.RequestHandler):
    def put(self):
        self.settings.sfx.setVolume(float(self.get_argument('v')))
        return "ok"

class StopAll(cyclone.web.RequestHandler):
    def post(self):
        self.settings.sfx.stopAll()
        return "ok"


if __name__ == '__main__':
    arg = docopt('''
    Usage: playSound.py [options]

    -v                Verbose
    ''')
    verboseLogging(arg['-v'])

    os.environ['PULSE_SERVER'] = '172.17.0.1'
    sfx = SoundEffects()

    reactor.listenTCP(9049, cyclone.web.Application(handlers=[
        (r'/', Index),
        (r'/playSound', PlaySound),
        (r'/volume', Volume),
        (r'/stopAll', StopAll),
    ], template_path='.', sfx=sfx))
    reactor.run()
