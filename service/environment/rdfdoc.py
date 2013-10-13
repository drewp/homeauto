# to be shared somewhere
import json, cyclone.web
from cycloneerr import PrettyErrorHandler
from rdflib import Graph, RDFS, URIRef

graph = Graph()
graph.parse("docs.n3", format="n3")

# maybe the web page could just query sesame over http and we drop this server
class Doc(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        uri = URIRef(self.get_argument('uri'))

        ret = {}
        comment = graph.value(uri, RDFS.comment)
        if comment is not None:
            ret['comment'] = comment
        
        self.set_header("Content-type", "application/json")
        self.write(json.dumps(ret))
