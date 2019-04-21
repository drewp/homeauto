"""
statements about dhcp leases (and maybe live-host pings)

also read 'arp -an' and our dns list 
"""
import sys
import datetime
sys.path.append("/my/site/magma")
from stategraph import StateGraph
from rdflib import URIRef, Namespace, Literal, RDF, RDFS, XSD, ConjunctiveGraph
from dateutil.tz import tzlocal
import cyclone.web
from twisted.internet import reactor, task
from isc_dhcp_leases.iscdhcpleases import IscDhcpLeases
sys.path.append("/my/proj/homeauto/lib")
from patchablegraph import PatchableGraph, CycloneGraphEventsHandler, CycloneGraphHandler
sys.path.append("/my/proj/rdfdb")
from rdfdb.patch import Patch

DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")

def timeLiteral(dt):
    return Literal(dt.replace(tzinfo=tzlocal()).isoformat(),
                   datatype=XSD.dateTime)

def update(masterGraph):
    g = ConjunctiveGraph()
    ctx = DEV['dhcp']

    now = datetime.datetime.now()
    for mac, lease in IscDhcpLeases('/var/lib/dhcp/dhcpd.leases'
                                    ).get_current().items():
        uri = URIRef("http://bigasterisk.com/dhcpLease/%s" % lease.ethernet)

        g.add((uri, RDF.type, ROOM['DhcpLease'], ctx))
        g.add((uri, ROOM['leaseStartTime'], timeLiteral(lease.start), ctx))
        g.add((uri, ROOM['leaseEndTime'], timeLiteral(lease.end), ctx))
        if lease.end < now:
            g.add((uri, RDF.type, ROOM['ExpiredLease'], ctx))
        ip = URIRef("http://bigasterisk.com/localNet/%s/" % lease.ip)
        g.add((uri, ROOM['assignedIp'], ip, ctx))
        g.add((ip, RDFS.label, Literal(lease.ip), ctx))
        mac = URIRef("http://bigasterisk.com/mac/%s" % lease.ethernet)
        g.add((uri, ROOM['ethernetAddress'], mac, ctx))
        g.add((mac, ROOM['macAddress'], Literal(lease.ethernet), ctx))
        if lease.hostname:
            g.add((mac, ROOM['dhcpHostname'], Literal(lease.hostname), ctx))
    masterGraph.setToGraph(g)
        
if __name__ == '__main__':
    config = {
        'servePort' : 9073,
        }
    from twisted.python import log as twlog
    twlog.startLogging(sys.stdout)
    #log.setLevel(10)
    #log.setLevel(logging.DEBUG)
    masterGraph = PatchableGraph()
    task.LoopingCall(update, masterGraph).start(1)

    reactor.listenTCP(
        config['servePort'],
        cyclone.web.Application(
            [
                (r"/()", cyclone.web.StaticFileHandler,
                 {"path": ".", "default_filename": "index.html"}),
                
                (r'/graph', CycloneGraphHandler, {'masterGraph': masterGraph}),
                (r'/graph/events', CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
            ], masterGraph=masterGraph
        ))
    reactor.run()
