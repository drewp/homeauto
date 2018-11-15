from __future__ import division
import time
import numpy
import logging
import imageio
from rdflib import Namespace, RDF, URIRef, Literal

ROOM = Namespace('http://projects.bigasterisk.com/room/')
log = logging.getLogger()

def _rgbFromHex(h):
    rrggbb = h.lstrip('#')
    return [int(x, 16) for x in [rrggbb[0:2], rrggbb[2:4], rrggbb[4:6]]]

class PixelColumnsFromImages(object):
    # could use this instead:
    # https://github.com/OpenImageIO/oiio/blob/master/src/python/py_imagecache.cpp
    def __init__(self):
        self.lastImg = None, None

    def get(self, path, x, y, h):
        if self.lastImg[0] != path:
            fp = 'config/' + path
            self.lastImg = path, imageio.imread(fp) # or etcd or http
            log.debug('read image from %r', fp)
        img = self.lastImg[1]

        y = numpy.clip(y, 0, img.shape[0] - 1)
        h = numpy.clip(h, 1, img.shape[0] - y)
        x = numpy.clip(x, 0, img.shape[1] - 1)
        log.info('getcol y=%s h=%s img=%r ret=%r', y, h, img.shape, img[y:y + h,x,:].shape)
        return img[y:y + h,x,:]

getPixelColumn = PixelColumnsFromImages().get


class AnimChannel(object):
    def __init__(self, x):
        self.x = self.x2 = x
        self.start = self.end = 0

    def animTo(self, x2, rate):
        self.get() # bring self.x to current time
        log.info('animTo %s -> %s', self.x, x2)
        if x2 == self.x:
            return
        self.start = time.time()
        self.end = self.start + abs(x2 - self.x) / rate
        self.x0 = self.x
        self.x2 = x2

    def get(self):
        now = time.time()
        if now > self.end:
            self.x = self.x2
        else:
            dur = self.end - self.start
            self.x = (self.end - now) / dur * self.x0 + (now - self.start) / dur * self.x2
        return self.x

class ScanGroup(object):

    def __init__(self, uri, numLeds):
        self.uri = uri
        self.current = numpy.zeros((numLeds, 3), dtype=numpy.uint8)

        self.x = AnimChannel(0)
        self.y = AnimChannel(0)
        self.height = AnimChannel(numLeds)

    def animateTo(self, x, y, height, src, rate=30, interpolate=ROOM['slide']):
        log.info('anim to %s x=%s y=%s h=%s', src, x, y, height)
        self.x.animTo(x, rate)
        self.y.animTo(y, rate) # need separate y rate?
        self.height.animTo(height, rate)

        self.src = src

    def updateCurrent(self):
        try:
            self.current = getPixelColumn(self.src,
                                          int(self.x.get()),
                                          int(self.y.get()),
                                          int(self.height.get()))
        except IOError as e:
            log.warn('getPixelColumn %r', e)
        log.debug('current = %r', self.current)
        
    def currentStatements(self):
        return []

    def colorForIndex(self, i):
        return list(self.current[i,:])

args = {ROOM['src']: ('src', str),
        ROOM['x']: ('x', int),
        ROOM['y']: ('y', int),
        ROOM['height']: ('height', int),
        ROOM['interpolate']: ('interpolate', lambda x: x),
        ROOM['rate']: ('rate', float),
        }

    
class RgbPixelsAnimation(object):

    def __init__(self, graph, uri, updateOutput):
        """we call updateOutput after any changes"""
        self.graph = graph
        self.uri = uri
        self.updateOutput = updateOutput
        self.setupGroups()
        
    def setupGroups(self):
        self.groups = {}
        self.groupWithIndex = {}
        attrStatements = set()
        for grp in self.graph.objects(self.uri, ROOM['pixelGroup']):
            s = int(self.graph.value(grp, ROOM['startIndex']))
            e = int(self.graph.value(grp, ROOM['endIndex']))
            log.info('ScanGroup %s from %s to %s', grp, s, e)
            sg = ScanGroup(grp, e - s + 1)
            self.groups[grp] = [s, e, sg]
            for i in range(s, e + 1):
                self.groupWithIndex[i] = sg, i - s
            attrStatements.update(self.graph.triples((grp, None, None)))
        self.onStatements(attrStatements, _groups=False)
            
    def maxIndex(self):
        return max(v[1] for v in self.groups.itervalues())

    def hostStatements(self):
        return (
            [(self.uri, ROOM['pixelGroup'], grp) for grp in self.groups.keys()] +
            sum([v[2].currentStatements()
                 for v in self.groups.itervalues()], []))

    def getColorOrder(self, graph, uri):
        colorOrder = graph.value(uri, ROOM['colorOrder'],
                                 default=ROOM['ledColorOrder/RGB'])
        head, tail = str(colorOrder).rsplit('/', 1)
        if head != str(ROOM['ledColorOrder']):
            raise NotImplementedError('%r colorOrder %r' % (uri, colorOrder))
        stripType = None
        return colorOrder, stripType
        
    def step(self):
        # if animating...
        self.updateOutput()
        
    def onStatements(self, statements, _groups=True):

        needSetup = False
        animateCalls = {} # group uri : kw for animateTo
        for s, p, o in statements:
            if s not in self.groups:
                # missing the case that you just added a new group
                continue
            if p in args:
                k, conv = args[p]
                animateCalls.setdefault(s, {})[k] = conv(o.toPython())
            else:
                needSetup = True

        if needSetup and _groups:
            self.setupGroups()
        for grp, kw in animateCalls.items():
            for pred, (k, conv) in args.items():
                if k not in kw:
                    v = self.graph.value(grp, pred)
                    if v is not None:
                        kw[k] = conv(v.toPython())

            self.groups[grp][2].animateTo(**kw)

    def outputPatterns(self):
        pats = []
        for grp in self.groups:
            for attr in args:
                pats.append((grp, attr, None))
        return pats

    def outputWidgets(self):
        return []

    def currentColors(self):
        for _, _, sg in self.groups.values():
            sg.updateCurrent()
        for idx in range(self.maxIndex() + 1):
            sg, offset = self.groupWithIndex[idx]
            r, g, b = sg.colorForIndex(offset)
            yield idx, (r, g, b)
