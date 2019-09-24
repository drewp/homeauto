import logging, json, base64
from typing import List, Iterable

from cyclone.httpclient import fetch
from rdflib import Literal, Graph, RDF, URIRef, Namespace, RDFS
from twisted.internet.defer import inlineCallbacks, returnValue

log = logging.getLogger()
ROOM = Namespace("http://projects.bigasterisk.com/room/")
AST = Namespace("http://bigasterisk.com/")

def macUri(macAddress: str) -> URIRef:
    return URIRef("http://bigasterisk.com/mac/%s" % macAddress.lower())

class SeenNode(object):
    def __init__(self, uri: URIRef, mac: str, ip: str, stmts: Iterable):
        self.connected = True
        self.uri = uri
        self.mac = mac
        self.ip = ip
        self.stmts = stmts
    
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
        triples = set()
        uri = macUri(row['mac'].lower())
        
        if row['contype'] in ['2.4G', '5G']:
            orbi = macUri(row['conn_orbi_mac'])
            ct = ROOM['wifiBand/%s' % row['contype']]
            triples.add((uri, ROOM['connectedToAp'], orbi))
            triples.add((uri, ROOM['wifiBand'], ct))
            triples.add((orbi, RDF.type, ROOM['AccessPoint']))
            triples.add((orbi, ROOM['wifiBand'], ct))
            triples.add((orbi, ROOM['macAddress'],
                           Literal(row['conn_orbi_mac'].lower())))
            triples.add((orbi, RDFS.label, Literal(row['conn_orbi_name'])))
        elif row['contype'] == 'wireless':
            pass
        elif row['contype'] == 'wired':
            pass
        elif row['contype'] == '-':
            pass
        else:
            pass
        triples.add((uri, ROOM['connectedToNet'], ROOM['HouseOpenNet']))

        if row['model'] != 'Unknown':
            triples.add((uri, ROOM['networkModel'], Literal(row['model'])))
            
        rows.append(SeenNode(
            uri=uri,
            mac=row['mac'].lower(),
            ip=row['ip'],
            stmts=triples))
    returnValue(rows)
