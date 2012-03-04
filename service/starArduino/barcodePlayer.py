#!bin/python
"""
receives POSTs about barcodes that are scanned, plays songs on mpd
"""

from __future__ import division

import cyclone.web, cyclone.httpclient, sys, json
from twisted.python import log
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler



class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        
        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(open("index.html").read())

class BarcodeScan(PrettyErrorHandler, cyclone.web.RequestHandler):
    @inlineCallbacks
    def post(self):
        print json.loads(self.request.body)

        song = "cd/Kindermusik-The_Best_of_the_Best/14.Fiddle-de-dee.ogg"

        print (yield cyclone.httpclient.fetch(url="http://star:9009/addAndPlay/%s" % song, method="POST")).body

        self.write("ok")


if __name__ == '__main__':
    app = cyclone.web.Application([
        (r'/', Index),
        (r'/barcodeScan', BarcodeScan),
        ], )
    log.startLogging(sys.stdout)
    reactor.listenTCP(9011, app)
    reactor.run()
