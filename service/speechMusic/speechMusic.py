#!bin/python
"""
play sounds according to POST requests.
"""
from __future__ import division
import sys, tempfile, itertools
from pyjade.ext.mako import preprocessor as mako_preprocessor
from mako.lookup import TemplateLookup
from twisted.internet import reactor
from cyclone.httpclient import fetch
from generator import tts
import xml.etree.ElementTree as ET
from klein import Klein
from twisted.web.static import File
from logsetup import log
import pygame.mixer
class URIRef(str): pass

soundCount = itertools.count()
templates = TemplateLookup(directories=['.'],
                           preprocessor=mako_preprocessor,
                           filesystem_checks=True)

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
            t -= preEffectOverlap
            
        reactor.callLater(t, self.playBuffer, buf)
        t += secs

        if postEffect:
            self.playBufferLater(t, self.buffers[postEffect])

    def playBufferLater(self, t, buf):
        self.queued.append(reactor.callLater(t, self.playBuffer, buf))
            
    def playBuffer(self, buf):
        buf.play()

        secs = buf.get_length()
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

class Server(object):
    app = Klein()
    def __init__(self, sfx):
        self.sfx = sfx

    @app.route('/static/', branch=True)
    def static(self, request):
        return File("./static")

    @app.route('/', methods=['GET'])
    def index(self, request):
        t = templates.get_template("index.jade")
        return t.render(effectNames=[
            dict(name=k, postUri='effects/%s' % k)
            for k in self.sfx.buffers.keys()])

    @app.route('/speak', methods=['POST'])
    def speak(self, request):
        self.sfx.playSpeech(request.args['msg'][0])
        return "ok"

    @app.route('/playSound', methods=['POST'])
    def effect(self, request):
        uri = request.args['uri'][0]
        self.sfx.playEffect(uri)
        return "ok"

    @app.route('/volume', methods=['PUT'])
    def volume(self, request, name):
        self.sfx.setVolume(float(request.args['v'][0]))
        return "ok"

    @app.route('/stopAll', methods=['POST'])
    def stopAll(self, request):
        self.sfx.stopAll()
        return "ok"

pygame.mixer.init()
sfx = SoundEffects()

server = Server(sfx)
server.app.run(endpoint_description=r"tcp6:port=9049:interface=\:\:")
