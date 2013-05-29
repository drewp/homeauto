"""
talks to the arduino outside the front door. Don't write straight to
this LCD; use frontDoorMessage for that.

lcd is this wide
|-------------------|
22:05 85F in, 71F out

pin 11 senses the door
pin 12 activates the front yard lights ('out yard')

"""

from __future__ import division

import cyclone.web, json, traceback, os, sys
from twisted.python import log
from twisted.internet import reactor, task
from twisted.web.client import getPage
from rdflib import Namespace, Literal, URIRef

sys.path.append("/my/proj/house/frontdoor")
from loggingserial import LoggingSerial        

sys.path.append("/my/proj/homeauto/lib")
from cycloneerr import PrettyErrorHandler

sys.path.append("/my/site/magma")
from stategraph import StateGraph

DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

class Board(object):
    """
    arduino board actions, plus the last values we wrote to it
    """
    def __init__(self, port):
        self.ser = LoggingSerial(port=port)
        self.ser.flush()

        self.setLcd("")
        self.setLcdBrightness(0)
        self.setYardLight(0)

    def ping(self):
        self.getDoor()

    def getDoor(self):
        self.ser.write("\xff\x01")
        ret = self.ser.readJson()
        return ret['door']

    def setYardLight(self, level):
        self.currentYardLight = bool(level)
        self.ser.write("\xff\x04" + chr(bool(self.currentYardLight)))

    def getYardLight(self):
        return self.currentYardLight

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

class GraphResource(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        g = StateGraph(ctx=DEV['frontDoorArduino'])

        board = self.settings.board
        g.add((DEV['frontDoorOpen'], ROOM['state'],
               ROOM['open'] if board.getDoor() == 'open' else ROOM['closed']))
        g.add((DEV['frontYardLight'], ROOM['state'],
               ROOM['on'] if board.getYardLight() else ROOM['off']))
        g.add((DEV['frontDoorLcd'], ROOM['text'],
               Literal(board.getLcd())))
        g.add((DEV['frontDoorLcd'], ROOM['brightness'],
               Literal(board.getLcdBrightness())))

        # not temperature yet because it's slow and should be cached from
        # the last poll
        
        self.set_header('Content-type', 'application/x-trig')
        self.write(g.asTrig())

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


class YardLight(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({
            "yardLight" : self.settings.board.getYardLight()}))
        
    def put(self):
        """text true or false or 0 or 1"""
        self.settings.board.setYardLight(
            self.request.body.strip() in ['true', '1'])
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
            (r"/graph", GraphResource),
            (r'/lcd', Lcd),
            (r'/door', Door),
            (r'/temperature', Temperature),
            (r'/lcd/backlight', Backlight),
            (r'/yardLight', YardLight),
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
            # this should be fetching everything and pinging reasoning
            # if anything is new
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

    config = { # to be read from a file
        'arduinoPort': '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A6004bUG-if00-port0',
        'servePort' : 9080,
        'pollFrequency' : 1,
        'boardName' : 'frontDoor', # gets sent with updates
        'doorChangePost' : 'http://bang.bigasterisk.com:9069/inputChange',
        # todo: need options to preset inputs/outputs at startup
        }

    #log.startLogging(sys.stdout)

    board = Board(port=config['arduinoPort'])
    
    p = Poller(board, config['doorChangePost'], config['boardName'])
    task.LoopingCall(p.poll).start(1/config['pollFrequency'])
    reactor.listenTCP(config['servePort'], Application(board))
    reactor.run()
