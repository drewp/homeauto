import re, ast, logging, socket, json, base64
from twisted.internet.defer import inlineCallbacks, returnValue
from cyclone.httpclient import fetch
from rdflib import Literal, Graph, RDFS, URIRef

log = logging.getLogger()

def macUri(macAddress: str) -> URIRef:
    return URIRef("http://bigasterisk.com/mac/%s" % dev['mac'].lower())

class Wifi(object):
    """
    gather the users of wifi from the tomato routers
    """
    def __init__(self, accessN3="/my/proj/openid_proxy/access.n3"):
        self.rereadConfig()
        #self._loadRouters(accessN3, tomatoUrl)

    def rereadConfig(self):
        self.graph = Graph()
        self.graph.parse('config.n3', format='n3')
        
        
    def _loadRouters(self, accessN3, tomatoUrl):
        g = Graph()
        g.parse(accessN3, format="n3")
        repl = {
            '/wifiRouter1/' : None,
            #'/tomato2/' : None
        }
        for k in repl:
            rows = list(g.query('''
            PREFIX p: <http://bigasterisk.com/openid_proxy#>
            SELECT ?prefix WHERE {
              ?site
                p:requestPrefix ?public;
                p:proxyUrlPrefix ?prefix
                .
            }''', initBindings={"public" : Literal(k)}))
            repl[k] = str(rows[0][0])
        log.debug('repl %r', repl)

        self.routers = []
        for url in tomatoUrl:
            name = url
            for k, v in repl.items():
                url = url.replace(k, v)

            r = Router()
            http, tail = url.split('//', 1)
            userPass, tail = tail.split("@", 1)
            r.url = http + '//' + tail
            r.headers = {'Authorization': ['Basic %s' % userPass.encode('base64').strip()]}
            r.name = {'wifiRouter1' : 'bigasterisk5',
                      'tomato2' : 'bigasterisk4'}[name.split('/')[1]]
            self.routers.append(r)

    @inlineCallbacks
    def getPresentMacAddrs(self):
        self.rereadConfig()
        rows = yield loadOrbiData()
        for row in rows:
            if 'clientHostname' in row:
                row['name'] = row['clientHostname']
            mac = macUri(row['mac'].lower())
            label = self.graph.value(mac, RDFS.label)
            if label:
                row['name'] = label
        returnValue(rows)
            
    @inlineCallbacks
    def getPresentMacAddrs_multirouter(self):
        rows = []
        
        for router in self.routers:
            log.debug("GET %s", router)
            try:
                resp = yield fetch(router.url, headers=router.headers,
                                   timeout=2)
            except socket.error:
                log.warn("get on %s failed" % router)
                continue
            data = resp.body
            if 'Wireless -- Authenticated Stations' in data:
                # zyxel 'Station Info' page
                rows.extend(self._parseZyxel(data, router.name))
            else:
                # tomato page
                rows.extend(self._parseTomato(data, router.name))

        for r in rows:
            try:
                r['name'] = self.knownMacAddr[r['mac']]
            except KeyError:
                pass
                
        returnValue(rows)
        
    def _parseZyxel(self, data, routerName):
        import lxml.html.soupparser

        root = lxml.html.soupparser.fromstring(data)
        for tr in root.cssselect('tr'):
            mac, assoc, uth, ssid, iface = [td.text_content().strip() for td in tr.getchildren()]
            if mac == "MAC":
                continue
            assoc = assoc.lower() == 'yes'
            yield dict(router=routerName, mac=mac, assoc=assoc, connected=assoc)

    def _parseTomato(self, data, routerName):
        for iface, mac, signal in jsValue(data, 'wldev'):
            yield dict(router=routerName, mac=mac, signal=signal, connected=bool(signal))


@inlineCallbacks
def loadUvaData():
    import lxml.html.soupparser

    config = json.load(open("priv-uva.json"))
    headers = {'Authorization': ['Basic %s' % config['userPass'].encode('base64').strip()]}
    resp = yield fetch('http://10.2.0.2/wlstationlist.cmd', headers=headers)
    root = lxml.html.soupparser.fromstring(resp.body)
    byMac = {}
    for tr in root.cssselect('tr'):
        mac, connected, auth, ssid, iface = [td.text_content().strip() for td in tr.getchildren()]
        if mac == "MAC":
            continue
        connected = connected.lower() == 'yes'
        byMac[mac] = dict(mac=mac, connected=connected, auth=auth == 'Yes', ssid=ssid, iface=iface)
        
    resp = yield fetch('http://10.2.0.2/DHCPTable.asp', headers=headers)
    for row in re.findall(r'new AAA\((.*)\)', resp.body):
        clientHostname, ipaddr, mac, expires, iface = [s.strip("'") for s in row.rsplit(',', 4)]
        if clientHostname == 'wlanadv.none':
            continue
        byMac.setdefault(mac, {}).update(dict(
            clientHostname=clientHostname, connection=iface, ipaddr=ipaddr, dhcpExpires=expires))
    
    returnValue(sorted(byMac.values()))

@inlineCallbacks
def loadCiscoData():
    config = json.load(open("priv-uva.json"))
    headers = {'Authorization': ['Basic %s' % config['userPass'].encode('base64').strip()]}
    print(headers)
    resp = yield fetch('http://10.2.0.2/', headers=headers)
    print(resp.body)
    returnValue([])

@inlineCallbacks
def loadOrbiData():
    config = json.load(open("priv-uva.json"))
    headers = {b'Authorization': [
        b'Basic %s' % base64.encodebytes(config['userPass'].encode('utf8')).strip()]}
    resp = yield fetch(b'http://orbi.bigasterisk.com/DEV_device_info.htm', method=b'GET', headers=headers)
    print('back from fetch')

    if not resp.body.startswith((b'device=', b'device_changed=0\ndevice=', b'device_changed=1\ndevice=')):
        raise ValueError(resp.body)

    ret = []
    for row in json.loads(resp.body.split(b'device=', 1)[-1]):
        ret.append(dict(
            connected=True,
            ipaddr=row['ip'],
            mac=row['mac'].lower(),
            contype=row['contype'],
            model=row['model'],
            clientHostname=row['name'] if row['name'] != 'Unknown' else None))
    returnValue(ret)

            
def jsValue(js, variableName):
    # using literal_eval instead of json parser to handle the trailing commas
    val = re.search(variableName + r'\s*=\s*(.*?);', js, re.DOTALL).group(1)
    return ast.literal_eval(val)