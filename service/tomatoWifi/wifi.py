import re, ast, logging, socket
import lxml.html.soupparser
from twisted.internet.defer import inlineCallbacks, returnValue
from cyclone.httpclient import fetch
from rdflib import Literal, Graph

log = logging.getLogger()

class Router(object):
    def __repr__(self):
        return repr(self.__dict__)

class Wifi(object):
    """
    gather the users of wifi from the tomato routers

    with host names from /var/lib/dhcp/dhcpd.leases
    """
    def __init__(self, tomatoConfig="/my/site/magma/tomato_config.js",
                 accessN3="/my/proj/openid_proxy/access.n3"):

        # ideally this would all be in the same rdf store, with int and
        # ext versions of urls

        txt = open(tomatoConfig).read().replace('\n', '')
        self.knownMacAddr = jsValue(txt, 'knownMacAddr')
        tomatoUrl = jsValue(txt, 'tomatoUrl')

        g = Graph()
        g.parse(accessN3, format="n3")
        repl = {'/tomato1/' : None, '/tomato2/' : None}
        for k in repl:
            rows = list(g.query('''
            PREFIX p: <http://bigasterisk.com/openid_proxy#>
            SELECT ?prefix WHERE {
              [
                p:requestPrefix ?public;
                p:proxyUrlPrefix ?prefix
                ]
            }''', initBindings={"public" : Literal(k)}))
            repl[k] = str(rows[0][0])

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
            r.name = {'tomato1' : 'bigasterisk5',
                      'tomato2' : 'bigasterisk4'}[name.split('/')[1]]
            self.routers.append(r)

    @inlineCallbacks
    def getPresentMacAddrs(self):
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
                rows.extend(self.parseZyxel(data, router.name))
            else:
                # tomato page
                rows.extend(self.parseTomato(data, router.name))

        for r in rows:
            try:
                r['name'] = self.knownMacAddr[r['mac']]
            except KeyError:
                pass
                
        returnValue(rows)
        
    def parseZyxel(self, data, routerName):
        root = lxml.html.soupparser.fromstring(data)
        for tr in root.cssselect('tr'):
            mac, assoc, uth, ssid, iface = [td.text_content().strip() for td in tr.getchildren()]
            if mac == "MAC":
                continue
            assoc = assoc.lower() == 'yes'
            yield dict(router=routerName, mac=mac, assoc=assoc, connected=assoc)

    def parseTomato(self, data, routerName):
        for iface, mac, signal in jsValue(data, 'wldev'):
            yield dict(router=routerName, mac=mac, signal=signal, connected=bool(signal))
        
            
def jsValue(js, variableName):
    # using literal_eval instead of json parser to handle the trailing commas
    val = re.search(variableName + r'\s*=\s*(.*?);', js, re.DOTALL).group(1)
    return ast.literal_eval(val)
