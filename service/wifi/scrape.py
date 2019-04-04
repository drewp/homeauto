import logging, json, base64
from typing import List

from cyclone.httpclient import fetch
from rdflib import Literal, Graph, RDF, URIRef, Namespace
from twisted.internet.defer import inlineCallbacks, returnValue

log = logging.getLogger()
ROOM = Namespace("http://projects.bigasterisk.com/room/")
AST = Namespace("http://bigasterisk.com/")

def macUri(macAddress: str) -> URIRef:
    return URIRef("http://bigasterisk.com/mac/%s" % macAddress.lower())

class SeenNode(object):
    def __init__(self, uri: URIRef, mac: str, ip: str, pred_objs: List):
        self.connected = True
        self.uri = uri
        self.mac = mac
        self.ip = ip
        self.stmts = [(uri, p, o) for p, o in pred_objs]
    
class Wifi(object):
    """
    gather the users of wifi from the tomato routers
    """
    def __init__(self, config: Graph):
        self.config = config
        
    @inlineCallbacks
    def getPresentMacAddrs(self): # returnValue List[SeenNode]
        rows = yield self._loader()(self.config)
        returnValue(rows)

    def _loader(self):
        cls = self.config.value(ROOM['wifiScraper'], RDF.type)
        if cls == ROOM['OrbiScraper']:
            return loadOrbiData
        raise NotImplementedError(cls)


@inlineCallbacks
def loadOrbiData(config):
    user = config.value(ROOM['wifiScraper'], ROOM['user'])
    passwd = config.value(ROOM['wifiScraper'], ROOM['password'])
    basicAuth = '%s:%s' % (user, passwd)
    headers = {
        b'Authorization': [
            b'Basic %s' % base64.encodebytes(basicAuth.encode('utf8')).strip()],
    }
    uri = config.value(ROOM['wifiScraper'], ROOM['deviceInfoPage'])
    resp = yield fetch(uri.encode('utf8'), method=b'GET', headers=headers)

    if not resp.body.startswith((b'device=',
                                 b'device_changed=0\ndevice=',
                                 b'device_changed=1\ndevice=')):
        raise ValueError(resp.body)

    log.debug(resp.body)
    rows = []
    for row in json.loads(resp.body.split(b'device=', 1)[-1]):
        extra = []
        extra.append((ROOM['connectedToNetwork'], {
                    'wireless': AST['wifiAccessPoints'],
                    '2.4G': AST['wifiAccessPoints'],
                    '5G':  AST['wifiAccessPoints'],
                    '-': AST['wifiUnknownConnectionType'],
                    'Unknown': AST['wifiUnknownConnectionType'],
                    'wired': AST['houseOpenNet']}[row['contype']]))
        if row['model'] != 'Unknown':
            extra.append((ROOM['networkModel'], Literal(row['model'])))
            
        rows.append(SeenNode(
            uri=macUri(row['mac'].lower()),
            mac=row['mac'].lower(),
            ip=row['ip'],
            pred_objs=extra))
    returnValue(rows)
