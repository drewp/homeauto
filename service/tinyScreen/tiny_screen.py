from docopt import docopt
from patchablegraph import PatchableGraph, CycloneGraphHandler, CycloneGraphEventsHandler
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.parser import StringInputSource
from twisted.internet import reactor
import cyclone.web
import sys, logging, time, textwrap

from luma.core.interface.serial import spi
from luma.oled.device import ssd1331
from PIL import Image, ImageFont, ImageDraw
ROOM = Namespace('http://projects.bigasterisk.com/room/')

logging.basicConfig()
log = logging.getLogger()

class Screen(object):
    def __init__(self, spiDevice=1, rotation=0):
        self._initOutput(spiDevice, rotation)
        self.news = ""
        self.goalState = None
        self.animateTo(ROOM['boot'])

    def _stateImage(self, state):
        return Image.open('anim/%s.png' % state.rsplit('/')[-1])
        
    def _initOutput(self, spiDevice, rotation):
        self._dev = ssd1331(spi(device=spiDevice, port=0,
                                # lots of timeouts on the 12288-byte transfer without this
                                transfer_size=64,
                                bus_speed_hz=16000000,
                                gpio_RST=None),
                            rotation=rotation)
        
    def setContrast(self, contrast):
        """0..255"""
        self._dev.contrast(contrast)

    def hide(self):
        """Switches the display mode OFF, putting the device in low-power sleep mode."""
        self._dev.hide()

    def show(self):
        self._dev.show()

    def display(self, img):
        self._dev.display(img.convert(self._dev.mode))

    def animateTo(self, state):
        """
        boot
        sleep
        locked
        lockedUnknownKey
        unlockNews
        """
        if self.goalState == state:
            return
        self.goalState = state
        self.display(self._stateImage(state))
        if state == ROOM['unlockNews']:
            self.renderNews()

    def setNews(self, text):
        if self.news == text:
            return
        self.news = text
        if self.goalState == ROOM['unlockNews']:
            # wrong during animation
            self.renderNews()
        
    def renderNews(self):
        bg = self._stateImage(ROOM['unlockNews'])
        draw = ImageDraw.Draw(bg)

        font = ImageFont.truetype("font/Oswald-SemiBold.ttf", 12)
        #w, h = font.getsize('txt')
        for i, line in enumerate(
                textwrap.fill(self.news, width=12).splitlines()):
            draw.text((24, 0 + 10 * i), line, font=font)
        self.display(bg)
        
class ScreenSim(Screen):
    def _initOutput(self):
        self.windowScale = 2
        import pygame
        self.pygame = pygame
        pygame.init()
        self.surf = pygame.display.set_mode(
            (96 * self.windowScale, 64 * self.windowScale))
        time.sleep(.05) # something was causing the 1st update not to show
        
    def display(self, img):
        pgi = self.pygame.image.fromstring(
            img.tobytes(), img.size, img.mode)
        self.pygame.transform.scale(pgi, self.surf.get_size(), self.surf)
        self.pygame.display.flip()

def rdfGraphBody(body, headers):
    g = Graph()
    g.parse(StringInputSource(body), format='nt')
    return g

class OutputPage(cyclone.web.RequestHandler):
    def put(self):
        arg = self.request.arguments
        if arg.get('s') and arg.get('p'):
            subj = URIRef(arg['s'][-1])
            pred = URIRef(arg['p'][-1])
            turtleLiteral = self.request.body
            try:
                obj = Literal(float(turtleLiteral))
            except ValueError:
                obj = Literal(turtleLiteral)
            stmts = [(subj, pred, obj)]
        else:
            nt = self.request.body.replace("\\n", "\n") # wrong, but i can't quote right in curl
            g = rdfGraphBody(nt, self.request.headers)
            assert len(g)
            stmts = list(g.triples((None, None, None)))
        self._onStatement(stmts)
            
    def _onStatement(self, stmts):
        """
        (disp :brightness 1.0 . )
        (disp :state :locked . )
        (disp :state :sleep . )
        (disp :state :readKeyUnlock . disp :news "some news text" . )
        """
        disp = ROOM['frontDoorOled']
        for stmt in stmts:
            if stmt[:2] == (disp, ROOM['news']):
                self.settings.screen.setNews(stmt[2].toPython())
            elif stmt[:2] == (disp, ROOM['state']):
                self.settings.screen.animateTo(stmt[2])
            else:
                log.warn("ignoring %s", stmt)
    
if __name__ == '__main__':
    arg = docopt("""
    Usage: tiny_screen.py [options]

    -v   Verbose
    -x   Draw to X11 window, not output hardware
    """)
    log.setLevel(logging.WARN)
    if arg['-v']:
        from twisted.python import log as twlog
        twlog.startLogging(sys.stdout)
        log.setLevel(logging.DEBUG)

    masterGraph = PatchableGraph()

    if arg['-x']:
        screen = ScreenSim()
    else:
        screen = Screen(spiDevice=1)

    port = 10013
    reactor.listenTCP(port, cyclone.web.Application([
        (r"/()", cyclone.web.StaticFileHandler,
         {"path": ".", "default_filename": "index.html"}),
        (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
        (r"/graph/events", CycloneGraphEventsHandler,
         {'masterGraph': masterGraph}),
        (r'/output', OutputPage),
        ], screen=screen, masterGraph=masterGraph, debug=arg['-v']),
                      interface='::')
    log.warn('serving on %s', port)
    
    reactor.run()
