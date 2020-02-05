"""
statements about dhcp leases (and maybe live-host pings)

also read 'arp -an' and our dns list 
"""
import datetime, itertools, os

from docopt import docopt
from dateutil.tz import tzlocal
from rdflib import URIRef, Namespace, Literal, RDF, RDFS, XSD, ConjunctiveGraph
from twisted.internet import reactor, task
import cyclone.web

from greplin import scales
from greplin.scales.cyclonehandler import StatsHandler
from patchablegraph import PatchableGraph, CycloneGraphEventsHandler, CycloneGraphHandler
from standardservice.logsetup import log, verboseLogging

DEV = Namespace("http://projects.bigasterisk.com/device/")
ROOM = Namespace("http://projects.bigasterisk.com/room/")
ctx = DEV['dhcp']

STATS = scales.collection('/root',
                          scales.PmfStat('readLeases'),
                          scales.IntStat('filesDidntChange'),
                          )

def timeLiteral(dt):
    return Literal(dt.replace(tzinfo=tzlocal()).isoformat(),
                   datatype=XSD.dateTime)

def macUri(macAddress: str) -> URIRef:
    return URIRef("http://bigasterisk.com/mac/%s" % macAddress.lower())

class Poller:
    def __init__(self, graph):
        self.graph = graph
        self.fileTimes = {'/opt/dnsmasq/10.1/leases': 0, '/opt/dnsmasq/10.2/leases': 0}
        task.LoopingCall(self.poll).start(2)

    def anythingToRead(self):
        ret = False
        for f, t in self.fileTimes.items():
            mtime = os.path.getmtime(f)
            if mtime > t:
                self.fileTimes[f] = mtime
                ret = True
        return ret

    def poll(self):
        if not self.anythingToRead():
            STATS.filesDidntChange += 1
            return

        with STATS.readLeases.time():
            g = ConjunctiveGraph()
            for line in itertools.chain(*[open(f) for f in self.fileTimes]):
                # http://lists.thekelleys.org.uk/pipermail/dnsmasq-discuss/2016q2/010595.html
                expiration_secs, addr, ip, hostname, clientid = line.strip().split(' ')

                uri = macUri(addr)
                g.add((uri, RDF.type, ROOM['HasDhcpLease'], ctx))
                g.add((uri, ROOM['macAddress'], Literal(addr), ctx))
                g.add((uri, ROOM['assignedIp'], Literal(ip), ctx))

                if hostname != '*':
                    g.add((uri, ROOM['dhcpHostname'], Literal(hostname), ctx))

            self.graph.setToGraph(g)

if __name__ == '__main__':
    arg = docopt("""
    Usage: store.py [options]

    -v           Verbose
    --port PORT  Serve on port [default: 9073].
    """)

    verboseLogging(arg['-v'])

    masterGraph = PatchableGraph()
    poller = Poller(masterGraph)

    reactor.listenTCP(
        int(arg['--port']),
        cyclone.web.Application(
            [
                (r"/()", cyclone.web.StaticFileHandler,
                 {"path": ".", "default_filename": "index.html"}),
                (r'/graph/dhcpLeases', CycloneGraphHandler, {'masterGraph': masterGraph}),
                (r'/graph/dhcpLeases/events', CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
                (r'/stats/(.*)', StatsHandler, {'serverName': 'dhcpleases'}),
            ], masterGraph=masterGraph
        ))
    reactor.run()
