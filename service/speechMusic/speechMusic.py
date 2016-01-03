#!bin/python
"""
play sounds according to POST requests.
"""
from __future__ import division
import sys, tempfile, logging, pyjade
from pyjade.ext.mako import preprocessor as mako_preprocessor
from mako.template import Template
from mako.lookup import TemplateLookup
sys.path.append("python-openal")
import openal
from twisted.internet import reactor
sys.path.append("/my/proj/csigen")
from generator import tts
import xml.etree.ElementTree as ET
from klein import Klein
from twisted.web.static import File
logging.basicConfig(level=logging.INFO,
                    format="%(created)f %(asctime)s %(levelname)s %(message)s")
log = logging.getLogger()

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
    return openal.Buffer(speechWav.name), speechSecs

class SoundEffects(object):
    def __init__(self):
        # for names to pass to this, see alcGetString with ALC_ALL_DEVICES_SPECIFIER
        device = openal.Device()
        self.contextlistener = device.ContextListener()

        # also '/my/music/entrance/%s.wav' then speak "Neew %s. %s" % (sensorWords[data['sensor']], data['name']),

        print "loading"
        self.buffers = {
            'leave': openal.Buffer('/my/music/entrance/leave.wav'),
            'highlight' : openal.Buffer('/my/music/snd/Oxygen/KDE-Im-Highlight-Msg-44100.wav'),
            'question' : openal.Buffer('/my/music/snd/angel_ogg/angel_question.wav'),
            'jazztrumpet': openal.Buffer('/my/music/snd/sampleswap/MELODIC SAMPLES and LOOPS/Acid Jazz Trumpet Lines/acid-jazz-trumpet-11.wav'),
            'beep1': openal.Buffer('/my/music/snd/bxfr/beep1.wav'),
            'beep2': openal.Buffer('/my/music/snd/bxfr/beep2.wav'),
        }
        print "loaded sounds"
        self.playingSources = []
        self.queued = []

    def playEffect(self, name):
        return self.playBuffer(self.buffers[name])

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
        src = self.contextlistener.get_source()
        src.buffer = buf
        src.play()

        secs = buf.size / (buf.frequency * buf.channels * buf.bits / 8)
        self.playingSources.append(src)
        reactor.callLater(secs + .1, self.done, src)
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

    @app.route('/effects/<string:name>', methods=['POST'])
    def effect(self, request, name):
        self.sfx.playEffect(name)
        return "ok"

    @app.route('/stopAll', methods=['POST'])
    def stopAll(self, request):
        self.sfx.stopAll()
        return "ok"
        
sfx = SoundEffects()

server = Server(sfx)
server.app.run("::", 9049)
