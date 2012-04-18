#!bin/python
"""
receives POSTs about barcodes that are scanned, plays songs on mpd
"""

from __future__ import division

import cyclone.web, cyclone.httpclient, sys, json, urllib
from twisted.python import log
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from pymongo import Connection
mpdPaths = Connection("bang", 27017)['barcodePlayer']['mpdPaths']

class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.write("barcode player. POST to /barcodeScan")

class BarcodeScan(PrettyErrorHandler, cyclone.web.RequestHandler):
    @inlineCallbacks
    def post(self):
        code = json.loads(self.request.body)

        if not code['code'].startswith("music "):
            raise ValueError("this service only knows music barcodes, not %r" %
                             code)

        rows = list(mpdPaths.find({'_id' : int(code['code'].split()[1])}))
        if not rows:
            raise ValueError("code %r unknown" % code)

        song = rows[0]['mpdPath']

        post = "http://star:9009/addAndPlay/%s" % urllib.quote(song, safe='')
        result = (yield cyclone.httpclient.fetch(
            method="POST", url=post)).body
        print result
        self.write(result)


if __name__ == '__main__':
    app = cyclone.web.Application([
        (r'/', Index),
        (r'/barcodeScan', BarcodeScan),
        ], )
    log.startLogging(sys.stdout)
    reactor.listenTCP(9011, app)
    reactor.run()
