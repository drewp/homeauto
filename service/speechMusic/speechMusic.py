#!bin/python

"""
play sounds according to POST requests. cooperate with pubsubhubbub
"""
import web, sys, jsonlib, subprocess, os, tempfile, logging
from subprocess import check_call
sys.path.append("/my/proj/csigen")
from generator import tts
import xml.etree.ElementTree as ET
logging.basicConfig(level=logging.INFO, format="%(created)f %(asctime)s %(levelname)s %(message)s")
log = logging.getLogger()

sensorWords = {"wifi" : "why fi",
               "bluetooth" : "bluetooth"}

def aplay(device, filename):
    paDeviceName = {
        'garage' : 'alsa_output.pci-0000_01_07.0.analog-stereo',
        'living' : 'alsa_output.pci-0000_00_04.0.analog-stereo',
        }[device]
    subprocess.call(['paplay',
                     '-d', paDeviceName,
                     filename])

def soundOut(preSound=None, speech='', postSound=None, fast=False):

    speechWav = tempfile.NamedTemporaryFile(suffix='.wav')

    root = ET.Element("SABLE")
    r = ET.SubElement(root, "RATE",
                      attrib=dict(SPEED="+50%" if fast else "+0%"))
    for sentence in speech.split('.'):
        div = ET.SubElement(r, "DIV")
        div.set("TYPE", "sentence")
        div.text = sentence

    sounds = []
    delays = []

    if preSound is not None:
        sounds.append(preSound)
        delays.extend([0,0]) # assume stereo
    
    speechSecs = tts(root, speechWav.name)
    sounds.append(speechWav.name)
    delays.append(.4)
    if postSound is not None:
        sounds.append(postSound)
        delays.extend([speechSecs + .4]*2) # assume stereo
    
    if len(sounds) == 1:
        outName = sounds[0]
    else:
        outWav = tempfile.NamedTemporaryFile(suffix='.wav')
        check_call(['/usr/bin/sox', '--norm', '--combine', 'merge',
                    ]+sounds+[
                    outWav.name,
                    'delay', ]+map(str, delays)+[
                    'channels', '1'])
        outName = outWav.name

    aplay('living', outName)

class visitorNet(object):
    def POST(self):
        data = jsonlib.loads(web.data())

        if data.get('action') == 'arrive':
            
            snd = ('/my/music/entrance/%s.wav' %
                   data['name'].replace(' ', '_').replace(':', '_'))
            if not os.path.exists(snd):
                snd = None

            soundOut(preSound="/my/music/snd/angel_ogg/angel_question.wav",
                     # sic:
                     speech="Neew %s. %s" % (sensorWords[data['sensor']],
                                            data['name']),
                     postSound=snd, fast=True)
            return 'ok'

        if data.get('action') == 'leave':
            soundOut(preSound='/my/music/entrance/leave.wav',
                     speech="lost %s. %s" % (sensorWords[data['sensor']],
                                             data['name']),
                     fast=True)
            return 'ok'
        
        return "nothing to do"

class index(object):
    def GET(self):
        web.header('Content-type', 'text/html')
        return '''
<p><form action="speak" method="post">say: <input type="text" name="say"> <input type="submit"></form></p>
<p><form action="testSound" method="post"> <input type="submit" value="test sound"></form></p>
'''

class speak(object):
    def POST(self):
        txt = web.input()['say']
        log.info("speak: %r", txt)
        soundOut(preSound='/my/music/snd/Oxygen/KDE-Im-Highlight-Msg-44100.wav',
                 speech=txt)
        return "sent"

class testSound(object):
    def POST(self):
        soundOut(preSound='/my/music/entrance/leave.wav')
        return 'ok'

urls = (
    r'/', 'index',
    r'/speak', 'speak',
    r'/testSound', 'testSound',
    r'/visitorNet', 'visitorNet',
    )

app = web.application(urls, globals(), autoreload=True)

if __name__ == '__main__':
    sys.argv.append("9049")
    app.run()
