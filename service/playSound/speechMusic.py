"""
play sounds according to POST requests.
"""
from docopt import docopt
import cyclone.web
import sys, tempfile, itertools
from twisted.internet import reactor
from cyclone.httpclient import fetch
from generator import tts
import xml.etree.ElementTree as ET
from twisted.web.static import File
from standardservice.logsetup import log, verboseLogging
import os

soundCount = itertools.count()

def makeSpeech(speech, fast=False):
    speechWav = tempfile.NamedTemporaryFile(suffix='.wav')

    root = ET.Element("SABLE")
    r = ET.SubElement(root, "RATE",
                      attrib=dict(SPEED="+50%" if fast else "+0%"))
    for sentence in speech.split('.'):
        div = ET.SubElement(r, "DIV")
        div.set("TYPE", "sentence")
        div.text = sentence

    speechSecs = tts(speech, speechWav.name)
    return pygame.mixer.Sound(speechWav.name), speechSecs

class LOADING(object): pass

class SoundEffects(object):
    def __init__(self):
        self.buffers = {} # URIRef : pygame.mixer.Sound
        self.playingSources = []
        self.queued = []
        self.volume = 1 # level for the next sound that's played (or existing instances of the same sound)

    def _getSound(self, uri):
        def done(resp):
            path = '/tmp/sound_%s' % next(soundCount)
            with open(path, 'w') as out:
                out.write(resp.body)
            log.info('write %s bytes to %s', len(resp.body), path)
            self.buffers[uri] = pygame.mixer.Sound(path)

        return fetch(uri).addCallback(done).addErrback(log.error)

    def playEffect(self, uri):
        if uri not in self.buffers:
            self.buffers[uri] = LOADING
            self._getSound(uri).addCallback(lambda ret: self.playEffect(uri))
            return
        if self.buffers[uri] is LOADING:
            # The first playback loads then plays, but any attempts
            # during that load are dropped, not queued.
            return
        snd = self.buffers[uri]
        snd.set_volume(self.volume)
        return self.playBuffer(snd)

    def playSpeech(self, txt, preEffect=None, postEffect=None, preEffectOverlap=0):
        buf, secs = makeSpeech(txt)
        t = 0
        if preEffect:
            t += self.playEffect(preEffect)

        self.playingSources.append(buf)
        reactor.callLater(secs + .1, self.done, buf)
        return secs

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
        self.render('index.html', effectNames=[
            dict(name=k, postUri='effects/%s' % k)
            for k in self.settings.sfx.buffers.keys()])

class Speak(cyclone.web.RequestHandler):
    def post(self):
        self.settings.sfx.playSpeech(self.get_argument('msg'))
        return "ok"

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

    import pygame
    print('mixer init pulse')
    import pygame.mixer
    pygame.mixer.init()
    sfx = SoundEffects()

    reactor.listenTCP(9049, cyclone.web.Application(handlers=[
        (r'/', Index),
        (r'/speak', Speak),
        (r'/playSound', PlaySound),
        (r'/volume', Volume),
        (r'/stopAll', StopAll),
        (r'/static/(.*)', cyclone.web.StaticFileHandler, {'path': 'static'}),
    ], template_path='.', sfx=sfx))
    reactor.run()
server.app.run(endpoint_description=r"tcp6:port=9049:interface=\:\:")
