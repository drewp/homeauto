"""
holds the current message on the front door lcd
"""
import cyclone.web, sys
import restkit
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler
from logsetup import log

class LcdParts(object):
    def __init__(self, putUrl):
        self.putUrl = putUrl
        log.info("restarting- message is now empty")
        self.message = ""
        self.lastLine = ""

    def updateLcd(self):
        whole = "%-147s%-21s" % (self.message, self.lastLine)
        restkit.request(url=self.putUrl,
                        method="PUT",
                        body=whole,
                        headers={"content-type":"text/plain"})
        
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
        'doorChangePost' : 'http://bang.bigasterisk.com:9069/inputChange',
        'servePort' : 9081,
        }

    lcdParts = LcdParts(config['frontDoorArduino'] + 'lcd')
    
    reactor.listenTCP(config['servePort'], Application(lcdParts))
    reactor.run()
