    
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

            
def jsValue(js, variableName):
    # using literal_eval instead of json parser to handle the trailing commas
    val = re.search(variableName + r'\s*=\s*(.*?);', js, re.DOTALL).group(1)
    return ast.literal_eval(val)

            
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
