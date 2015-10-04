"""
statements about dhcp leases (and maybe live-host pings)
"""
import sys
import datetime
sys.path.append("/my/site/magma")
from stategraph import StateGraph
from rdflib import URIRef, Namespace, Literal, RDF, RDFS, XSD
from dateutil.tz import tzlocal
import cyclone.web
from twisted.internet import reactor
from isc_dhcp_leases.iscdhcpleases import IscDhcpLeases

DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

def timeLiteral(dt):
    return Literal(dt.replace(tzinfo=tzlocal()).isoformat(),
                   datatype=XSD.dateTime)

class GraphHandler(cyclone.web.RequestHandler):
    def get(self):
        pruneExpired = bool(self.get_argument('pruneExpired', ''))
        g = StateGraph(ctx=DEV['dhcp'])

        now = datetime.datetime.now()
        for mac, lease in IscDhcpLeases('/var/lib/dhcp/dhcpd.leases'
                                        ).get_current().items():
            if pruneExpired and lease.end < now:
                continue
            uri = URIRef("http://bigasterisk.com/dhcpLease/%s" % lease.ethernet)
            
            g.add((uri, RDF.type, ROOM['DhcpLease']))
            g.add((uri, ROOM['leaseStartTime'], timeLiteral(lease.start)))
            g.add((uri, ROOM['leaseEndTime'], timeLiteral(lease.end)))
            ip = URIRef("http://bigasterisk.com/localNet/%s/" % lease.ip)
            g.add((uri, ROOM['assignedIp'], ip))
            g.add((ip, RDFS.label, Literal(lease.ip)))
            mac = URIRef("http://bigasterisk.com/mac/%s" % lease.ethernet)
            g.add((uri, ROOM['ethernetAddress'], mac))
            g.add((mac, ROOM['macAddress'], Literal(lease.ethernet)))
            if lease.hostname:
                g.add((mac, ROOM['dhcpHostname'], Literal(lease.hostname)))

        self.set_header('Content-Type', 'application/x-trig')
        self.write(g.asTrig())
        
if __name__ == '__main__':
    config = {
        'servePort' : 9073,
        }
    from twisted.python import log as twlog
    twlog.startLogging(sys.stdout)
    #log.setLevel(10)
    #log.setLevel(logging.DEBUG)

    reactor.listenTCP(
        config['servePort'],
        cyclone.web.Application(
            [
                (r"/()", cyclone.web.StaticFileHandler,
                 {"path": ".", "default_filename": "index.html"}),
                
                (r'/graph', GraphHandler),
            ],
        ))
    reactor.run()
