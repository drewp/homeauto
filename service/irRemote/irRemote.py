#!/usr/bin/env python

# Read lirc output, in order to sense key presses on an IR remote.
# There are various Python packages that claim to do this but
# they tend to require elaborate setup and I couldn't get any to work.
# This approach requires a lircd.conf but does not require a lircrc.
# If irw works, then in theory, this should too.
# Based on irw.c, https://github.com/aldebaran/lirc/blob/master/tools/irw.c


import socket
import logging
import requests
from rdflib import Graph, Namespace

ROOM = Namespace("http://projects.bigasterisk.com/room/")
SOCKPATH = "/var/run/lirc/lircd"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

class Listener:
    def __init__(self):
        self.lastKey = None, None
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        log.info('starting up on %s', SOCKPATH)
        self.sock.connect(SOCKPATH)

    def run(self):
        while True:
            keyname, updown = self.next_key()
            log.debug('%r (%r)', keyname, updown)
            if self.lastKey[0] is None or (
                    keyname == self.lastKey[0] and
                    updown < self.lastKey[1]):
                g = Graph()
                g.add((ROOM['remoteButton/%s' % keyname],
                       ROOM['state'],
                       ROOM['press']))
                nt = g.serialize(format='n3')
                resp = requests.post('http://bang6:9071/oneShot', headers={
                    'Content-Type': 'text/n3',
                    'user-agent': 'irRemote',
                }, data=nt)
                log.info('new press: %r', keyname)
                if resp.status_code != 200:
                    log.warning('reasoning responded with %s. %r',
                                resp.status_code, resp.__dict__)
            self.lastKey = keyname, updown
        
    def next_key(self):
        '''Get the next key pressed. Return keyname, updown.
        '''
        while True:
            data = self.sock.recv(128)
            # print("Data: " + data)
            data = data.strip()
            if data:
                break

        words = data.split()
        try:
            return words[2].decode('ascii'), int(words[1], 16)
        except:
            log.warning('failed on %r', data)
            raise

if __name__ == '__main__':
    Listener().run()


