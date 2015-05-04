import re, ast, logging, socket, json
import lxml.html.soupparser
from twisted.internet.defer import inlineCallbacks, returnValue
from cyclone.httpclient import fetch
from rdflib import Literal, Graph, RDFS, URIRef

log = logging.getLogger()

class Router(object):
    def __repr__(self):
        return repr(self.__dict__)

class Wifi(object):
    """
    gather the users of wifi from the tomato routers
    """
    def __init__(self, accessN3="/my/proj/openid_proxy/access.n3"):
        self.graph = Graph()
        self.graph.parse('config.n3', format='n3')

        #self._loadRouters(accessN3, tomatoUrl)
        
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
        rows = yield loadUvaData()
        for row in rows:
            if 'clientHostname' in row:
                row['name'] = row['clientHostname']
            mac = URIRef('http://bigasterisk.com/mac/%s' % row['mac'].lower())
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
    config = json.load(open("/my/proj/homeauto/service/tomatoWifi/priv-uva.json"))
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
    
            
def jsValue(js, variableName):
    # using literal_eval instead of json parser to handle the trailing commas
    val = re.search(variableName + r'\s*=\s*(.*?);', js, re.DOTALL).group(1)
    return ast.literal_eval(val)
