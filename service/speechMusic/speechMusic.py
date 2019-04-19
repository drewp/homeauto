#!bin/python
"""
play sounds according to POST requests.
"""
from __future__ import division
import sys, tempfile
from pyjade.ext.mako import preprocessor as mako_preprocessor
from mako.lookup import TemplateLookup
from twisted.internet import reactor
sys.path.append("/opt")
from generator import tts
import xml.etree.ElementTree as ET
from klein import Klein
from twisted.web.static import File
from logsetup import log
import pygame.mixer

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

    speechSecs = tts(root, speechWav.name)
    return pygame.mixer.Sound(speechWav.name), speechSecs

class SoundEffects(object):
    def __init__(self):

        # also '/my/music/entrance/%s.wav' then speak "Neew %s. %s" % (sensorWords[data['sensor']], data['name']),

        log.info("loading")
        self.buffers = {name.rsplit('.', 1)[0]: pygame.mixer.Sound('sound/%s' % name) for name in os.listdir('sound')}
        log.info("loaded sounds")
        self.playingSources = []
        self.queued = []
        self.volume = 1 # level for the next sound that's played (or existing instances of the same sound)

    def playEffect(self, name):
        snd = self.buffers[name]
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
    def effect(self, request, name):
        self.sfx.setVolume(float(request.args['msg'][0]))
        return "ok"

    @app.route('/stopAll', methods=['POST'])
    def stopAll(self, request):
        self.sfx.stopAll()
        return "ok"

pygame.mixer.init()
sfx = SoundEffects()

server = Server(sfx)
server.app.run(endpoint_description=r"tcp6:port=9049:interface=\:\:")
