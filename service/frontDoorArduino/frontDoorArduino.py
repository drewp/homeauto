"""
talks to the arduino outside the front door. Don't write straight to
this LCD; use frontDoorMessage for that.

lcd is this wide
|-------------------|
22:05 85F in, 71F out

"""

from __future__ import division

import cyclone.web, json, traceback, os, sys
from twisted.python import log
from twisted.internet import reactor, task
from twisted.web.client import getPage

sys.path.append("/my/proj/house/frontdoor")
from loggingserial import LoggingSerial        

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler

class Board(object):
    """
    arduino board actions, plus the last values we wrote to it
    """
    def __init__(self, port):
        self.ser = LoggingSerial(port=port)
        self.ser.flush()

        self.ser.write("\xff\x00\x00")
        self.ser.write("\xff\x03\x00")
        self.currentText = ""
        self.currentBrightness = 0

    def ping(self):
        self.getDoor()

    def getDoor(self):
        self.ser.write("\xff\x01")
        ret = self.ser.readJson()
        return ret['door']

    def getLcd(self):
        return self.currentText
        
    def setLcd(self, txt):
        """
        up to 8*21 chars
        """
        self.currentText = txt
        self.ser.write("\xff\x00" + txt + "\x00")

    def getLcdBrightness(self):
        return self.currentBrightness

    def setLcdBrightness(self, b):
        """b in 0 to 255"""
        self.currentBrightness = b
        self.ser.write("\xff\x03" + chr(b))

    def getTemperature(self):
        """returns parsed json from the board"""
        self.ser.write("\xff\x02")
        # this can take 1.25 seconds per retry
        f = self.ser.readJson()

        if f['temp'] > 184 or f['temp'] < -100:
            # this fails a lot, maybe 50% of the time. retry if 
            # you want
            raise ValueError("out of range temp value (%s)" % f)
        return f
    
class index(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.settings.board.ping()
        
        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(open("index.html").read())

class Lcd(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain")
        self.write(self.settings.board.getLcd())
        
    def put(self):
        self.settings.board.setLcd(self.request.body)
        self.set_status(204)

class Backlight(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({
            "backlight" : self.settings.board.getLcdBrightness()}))
        
    def put(self):
        """param brightness=0 to brightness=255"""
        self.settings.board.setLcdBrightness(
            int(self.get_argument('brightness')))
        self.write("ok")
    post = put

class Door(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain")
        self.write(self.settings.board.getDoor())

class Temperature(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        f = self.settings.board.getTemperature()
        self.set_header("Content-Type", "application/json")        
        self.write(f)
        
class Application(cyclone.web.Application):
    def __init__(self, board):
        handlers = [
            (r"/", index),
            (r'/lcd', Lcd),
            (r'/door', Door),
            (r'/temperature', Temperature),
            (r'/lcd/backlight', Backlight),
        ]
        settings = {"board" : board}
        cyclone.web.Application.__init__(self, handlers, **settings)


class Poller(object):
    def __init__(self, board, postUrl, boardName):
        self.board = board
        self.postUrl = postUrl
        self.boardName = boardName
        self.last = None

    def poll(self):
        try:
            new = self.board.getDoor()
            if new != self.last:
                msg = json.dumps(dict(board=self.boardName, 
                                      name="frontDoor", state=new))
                getPage(self.postUrl,
                        method="POST",
                        postdata=msg,
                        headers={'Content-Type' : 'application/json'}
                        ).addErrback(self.reportError, msg)

            self.last = new
        except (IOError, OSError):
            os.abort()
        except Exception, e:
            print "poll error", e
            traceback.print_exc()
            
    def reportError(self, msg, *args):
        print "post error", msg, args

if __name__ == '__main__':

    port = '/dev/ttyUSB0'
    if not os.path.exists(port):
        port = '/dev/ttyUSB1'

    config = { # to be read from a file
        'arduinoPort': port,
        'servePort' : 9080,
        'pollFrequency' : 1,
        'boardName' : 'frontDoor', # gets sent with updates
        'doorChangePost' : 'http://bang.bigasterisk.com:9069/inputChange',
        # todo: need options to preset inputs/outputs at startup
        }

    log.startLogging(sys.stdout)

    board = Board(port=config['arduinoPort'])
    
    p = Poller(board, config['doorChangePost'], config['boardName'])
    task.LoopingCall(p.poll).start(1/config['pollFrequency'])
    reactor.listenTCP(config['servePort'], Application(board))
    reactor.run()
