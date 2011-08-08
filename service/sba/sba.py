from __future__ import division
import serial, time, jsonlib, sys, cgi, argparse
import cyclone.web
from twisted.python import log
from twisted.internet import reactor

class Sba(object):
    def __init__(self, port="/dev/ttyACM0"):
        self.port = port
        self.reset()

    def reset(self):
        log.msg("reopening port")
        self.s = serial.Serial(self.port, baudrate=115200)
        log.msg(str(self.s.__dict__))
        self.sendControl()

    def sendControl(self):
        controlBits = [0, 1,
                       0, 0, 0,
                       1, 1, 1, 1, 1, 1, 1, # b correction
                       0, 0, 0,
                       1, 1, 1, 1, 1, 1, 1, # g correction
                       0,
                       0, 0, # clock mode 00=internal
                       1, 1, 1, 1, 1, 1, 1, # r correction
                       ]

        control = reduce(lambda a, b: a<<1 | b,
                         #controlBits
                         reversed(controlBits)
                         )
        self.send("C" + hex(control)[2:].zfill(8))
        self.send("E0")
        
    def send(self, cmd, getResponse=True):
        """
        send a command using the protocol from http://engr.biz/prod/SB-A/

        we will attach the carriage return, cmd is just a string like 'V'

        Returns the response line, like '+OK'
        """
        try:
            self.s.write(cmd + "\r")
        except OSError:
            self.reset()
            
        if getResponse:
            return self.s.readline().strip()

    def rgbs(self, rgbs):
        """
        send a set of full rgb packets. Values are 0..1023.
        """
        t1 = time.time()
        for (r,g,b) in rgbs:
            packed = (b & 0x3ff) << 20 | (r & 0x3ff) << 10 | (g & 0x3ff)
            self.send("D%08x" % packed, getResponse=False)

        self.send("L1", getResponse=False)
        self.send("L0", getResponse=False)
        sends = time.time() - t1
        # doing all the reads together triples the transmission rate
        t2 = time.time()
        [self.s.readline() for loop in range(2 + len(rgbs))]
        reads = time.time() - t2

        log.msg("%.1f ms for sends, %.1f ms for reads" % (
            1000 * sends, 1000 * reads))

class BriteChain(object):
    def __init__(self, sba):
        self.sba = sba
        self.colors = []

    def setColor(self, pos, color):
        """color is (r,g,b) 10-bit int. The highest position you ever
        set is how many channels we'll output"""
        if len(self.colors) <= pos:
            self.colors.extend([(0,0,0)]*(pos - len(self.colors) + 1))
        self.colors[pos] = color
        self.refresh()
        
    def getColor(self, pos):
        try:
            return self.colors[pos]
        except IndexError:
            return (0,0,0)

    def refresh(self):
        self.sba.rgbs(self.colors[::-1])

class IndexHandler(cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-type", "text/html")
        self.write(open("sba.html").read())

class BriteHandler(cyclone.web.RequestHandler):
    """
    /brite/0 is the first shiftbrite on the chain. Put a text/plain
    color like #ffffff (8-bit) or a application/json value like
    {"rgb10":[1023,1023,1023]} (for 10-bit). GET (with accept, to pick
    your format) to learn the current color. 

    /brite/1 affects the second shiftbrite on the chain, etc 
    """
    def put(self, pos):
        d = self.request.body
        ctype = self.request.headers.get("Content-Type")
        if ';' in ctype: 
            ctype = ctype.split(';')[0].strip()
        if ctype == 'text/plain':
            color = decode8bitHexColor(d)
        elif ctype == 'application/json':
            color = jsonlib.read(d)['rgb10']
        elif ctype == 'application/x-www-form-urlencoded':
            color = decode8bitHexColor(cgi.parse_qs(d)['color'][0])
        else:
            self.response.set_status(415, "use text/plain, application/json, "
                                     "or application/x-www-form-urlencoded")
            return

        self.settings.chain.setColor(int(pos), color)
        self.set_header("Content-Type", "text/plain")
        self.write("set %s\n" % pos)

    def post(self, pos):
        self.put(pos)
        self.redirect("..")

    def get(self, pos):
        # todo: content neg
        color = self.settings.chain.getColor(int(pos))
        self.set_header("Content-Type", "text/plain")
        self.write(encode8bitHexColor(color))

def decode8bitHexColor(s):
    return [4 * int(s.lstrip('#')[i:i+2], 16) for i in [0, 2, 4]]
def encode8bitHexColor(color):
    return "#%02X%02X%02X" % (color[0] // 4, color[1] // 4, color[2] // 4)

class Application(cyclone.web.Application):
    def __init__(self, chain):
        handlers = [
            (r"/", IndexHandler),
            (r"/brite/(\d+)", BriteHandler),
            ]

        settings = {
            "static_path": "./static",
            "template_path": "./template",
            "chain" : chain,
        }

        cyclone.web.Application.__init__(self, handlers, **settings)

def main():
    parser = argparse.ArgumentParser(description='drive sba lights')
    parser.add_argument('-v', '--verbose', action="store_true", help='logging')
    args = parser.parse_args()

    try:
        sba = Sba()
    except serial.SerialException:
        sba = Sba("/dev/ttyACM1")

    chain = BriteChain(sba)

    if 0: # todo: stick test patterns like this on some other resource
        while 1:
            t1 = time.time()
            steps = 0
            for x in range(0, 1024, 5):
                steps += 1
                sba.rgbs([(x, x, x)] * 2)
            print steps / (time.time() - t1)

    if args.verbose:
        log.startLogging(sys.stdout)
    reactor.listenTCP(9060, Application(chain))
    reactor.run()

if __name__ == "__main__":
    main()
