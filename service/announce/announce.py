"""
run TTS and send speech or other sounds to playSound and to chromecasts
"""
import subprocess, time, re

from docopt import docopt
from lru import LRU
from twisted.internet import utils, reactor
from twisted.internet.defer import inlineCallbacks
from urllib.parse import urlencode
import cyclone.web
import treq

from standardservice.logsetup import log, verboseLogging


recentFiles = LRU(50)


class Index(cyclone.web.RequestHandler):
    def get(self):
        self.render('index.html')


class PostAnnouncement(cyclone.web.RequestHandler):
    @inlineCallbacks
    def post(self):
        text = self.get_argument('text')
        evType = self.get_argument('evType', default=None)
        if evType is not None:
            text = f'<prosody rate="-10%" pitch="+30%">{evType}!</prosody>' + text

        url = yield tts(text)

        yield treq.post(r'http://dash:9049/playSound', params={b'uri': url})
        #chromecastPlay('10.2.0.60', url) # ari
        #chromecastPlay('10.2.0.61', url) # bed
        #chromecastPlay('10.2.0.62', url) # asher

        return url

@inlineCallbacks
def chromecastPlay(ip, url, volume=None):
    cmdPrefix = ['/opt/cast', '--timeout', '3s', '--host', ip]

    if volume is not None:
        m = re.search(r'Volume: [\.0-9]+',
                      subprocess.check_output(cmdPrefix + ['status']))
        oldVolume = float(m.group(1))
        subprocess.check_output(cmdPrefix + ['volume', str(volume)])

    output = yield utils.getProcessValue(
        cmdPrefix[0], args=cmdPrefix[1:] + [
            'media', 'play', url.decode('utf8')])
    print('cast out', output)

    if volume is not None:
        subprocess.check_call(cmdPrefix + ['volume', str(oldVolume)])


class Data(cyclone.web.RequestHandler):
    def get(self, which):
        print('getting ', which)
        self.set_header('Content-Type', 'audio/wav')
        self.write(recentFiles[which])


@inlineCallbacks
def tts(input_xml, affect='surprise', ptype='disagree'):
    mary_host = "172.17.0.1"
    mary_port = "59125"

    maryxml = f'''<?xml version="1.0" encoding="UTF-8" ?>
<maryxml version="0.4"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns=" http://mary.dfki.de/2002/MaryXML"
 xml:lang="en-US">
  <p>
   {input_xml}
  </p>
</maryxml>'''

    query_hash = {"INPUT_TEXT": maryxml,
                  "INPUT_TYPE": "RAWMARYXML",
                  "LOCALE": "en_US",
                  "VOICE": "cmu-slt-hsmm",
                  "OUTPUT_TYPE": "AUDIO",
                  "AUDIO": "WAVE",
                  }
    query = urlencode(query_hash).replace('+', '%20')

    resp = yield treq.post(
        "http://%s:%s/process?" % (mary_host, mary_port) + query)
    wav = yield treq.content(resp)
    which = '%.1f' % time.time()
    recentFiles[which] = wav
    url = f'http://10.2.0.1:9010/data/{which}'
    print('save', len(wav), 'bytes at', url)
    return url.encode('ascii')


if __name__ == '__main__':
    arg = docopt('''
    Usage: announce.py [options]

    -v                Verbose
    ''')
    verboseLogging(arg['-v'])

    reactor.listenTCP(9010, cyclone.web.Application(handlers=[
        (r'/', Index),
        (r'/announcement', PostAnnouncement),
        (r'/data/(.*)', Data),
    ], template_path='.'))
    reactor.run()
