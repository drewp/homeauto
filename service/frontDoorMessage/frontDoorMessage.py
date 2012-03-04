"""
holds the current message on the front door lcd
"""
import cyclone.web, sys, socket
import restkit
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

class LcdParts(object):
    def __init__(self, putUrl, pingUrl):
        self.putUrl, self.pingUrl = putUrl, pingUrl
        log.info("restarting- message is now empty")
        self.message = ""
        self.lastLine = ""

    def updateLcd(self):
        whole = "%-147s%-21s" % (self.message, self.lastLine)
        try:
            restkit.request(url=self.putUrl,
                            method="PUT",
                            body=whole,
                            headers={"content-type":"text/plain"})
        except socket.error, e:
            log.warn("update lcd failed, %s" % e)

        try:
            restkit.request(url=self.pingUrl, method="POST", body="")
        except socket.error, e:
            log.warn("ping failed, %s" % e)
        
class Index(PrettyErrorHandler, cyclone.web.RequestHandler):
    @inlineCallbacks
    def get(self):

        # refresh output, and make an error if we can't talk to them
        yield self.settings.lcdParts.updateLcd()
        
        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(open("index.html").read())

def getArg(s):
    return s.request.body.encode("ascii")

class Message(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain")
        self.write(self.settings.lcdParts.message)

    def put(self):
        self.settings.lcdParts.message = getArg(self)
        self.settings.lcdParts.updateLcd()
        self.set_status(204)

class LastLine(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain")
        self.write(self.settings.lcdParts.lastLine)

    def put(self):
        self.settings.lcdParts.lastLine = getArg(self)
        self.settings.lcdParts.updateLcd()
        self.set_status(204)

class Application(cyclone.web.Application):
    def __init__(self, lcdParts):
        handlers = [
            (r"/", Index),
            (r"/message", Message),
            (r'/lastLine', LastLine),
        ]
        settings = {"lcdParts" : lcdParts}
        cyclone.web.Application.__init__(self, handlers, **settings)

if __name__ == '__main__':

    config = {
        'frontDoorArduino': "http://slash:9080/",
        'doorChangePost' : 'http://bang:8014/frontDoorChange',
        'servePort' : 9081,
        }

    lcdParts = LcdParts(config['frontDoorArduino'] + 'lcd',
                        config['doorChangePost'])
    
    reactor.listenTCP(config['servePort'], Application(lcdParts))
    reactor.run()
