import re, ast, logging, socket
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
            r.name = {'tomato1' : 'bigasterisk3',
                      'tomato2' : 'bigasterisk4'}[name.split('/')[1]]
            self.routers.append(r)

    @inlineCallbacks
    def getPresentMacAddrs(self):
        aboutIp = {}
        byMac = {} # mac : [ip]

        for router in self.routers:
            log.debug("GET %s", router)
            try:
                resp = yield fetch(router.url, headers=router.headers,
                                   timeout=2)
            except socket.error:
                log.warn("get on %s failed" % router)
                continue
            data = resp.body

            for (ip, mac, iface) in jsValue(data, 'arplist'):
                aboutIp.setdefault(ip, {}).update(dict(
                    ip=ip,
                    router=router.name,
                    mac=mac,
                    iface=iface,
                    ))

                byMac.setdefault(mac, set()).add(ip)

            for (name, ip, mac, lease) in jsValue(data, 'dhcpd_lease'):
                if lease.startswith('0 days, '):
                    lease = lease[len('0 days, '):]
                aboutIp.setdefault(ip, {}).update(dict(
                    router=router.name,
                    rawName=name,
                    mac=mac,
                    lease=lease
                    ))

                byMac.setdefault(mac, set()).add(ip)

            for iface, mac, signal in jsValue(data, 'wldev'):
                matched = False
                for addr in aboutIp.values():
                    if (addr['router'], addr['mac']) == (router.name, mac):
                        addr.update(dict(signal=signal, iface=iface))
                        matched = True
                if not matched:
                    aboutIp["mac-%s-%s" % (router, mac)] = dict(
                        router=router.name,
                        mac=mac,
                        signal=signal,
                        )

        ret = []
        for addr in aboutIp.values():
            if addr.get('ip') in ['192.168.1.1', '192.168.1.2', '192.168.0.2']:
                continue
            try:
                addr['name'] = self.knownMacAddr[addr['mac']]
            except KeyError:
                addr['name'] = addr.get('rawName')
                if addr['name'] in [None, '*']:
                    addr['name'] = 'unknown'
            ret.append(addr)

        returnValue(ret)


def jsValue(js, variableName):
    # using literal_eval instead of json parser to handle the trailing commas
    val = re.search(variableName + r'\s*=\s*(.*?);', js, re.DOTALL).group(1)
    return ast.literal_eval(val)
