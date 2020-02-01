from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.parser import StringInputSource

ROOM = Namespace('http://projects.bigasterisk.com/room/')


def rdfGraphBody(body, headers):
    g = Graph()
    g.parse(StringInputSource(body), format='nt')
    return g


def expandQueryParamUri(txt) -> URIRef:
    if txt.startswith(':'):
        return ROOM[txt.lstrip(':')]
    # etc
    return URIRef(txt)


def rdfStatementsFromRequest(arg, body, headers):
    if arg.get('s') and arg.get('p'):
        subj = expandQueryParamUri(arg['s'][-1])
        pred = expandQueryParamUri(arg['p'][-1])
        turtleLiteral = body
        try:
            obj = Literal(float(turtleLiteral))
        except ValueError:
            obj = Literal(turtleLiteral)
        yield (subj, pred, obj)
    else:
        g = rdfGraphBody(body, headers)
        assert len(g) == 1, len(g)
        yield g.triples((None, None, None)).next()
        # could support multiple stmts
