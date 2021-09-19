import logging
from typing import List, Union, cast

from rdflib.graph import Graph
from rdflib.namespace import Namespace

from inference_types import Triple

log = logging.getLogger('infer')

ROOM = Namespace("http://projects.bigasterisk.com/room/")


def graphDump(g: Union[Graph, List[Triple]], oneLine=True):
    # this is very slow- debug only!
    if not log.isEnabledFor(logging.DEBUG):
        return "(skipped dump)"
    try:
        if not isinstance(g, Graph):
            g2 = Graph()
            g2 += g
            g = g2
        g.bind('', ROOM)
        g.bind('ex', Namespace('http://example.com/'))
        lines = cast(bytes, g.serialize(format='n3')).decode('utf8').splitlines()
        lines = [line for line in lines if not line.startswith('@prefix')]
        if oneLine:
            lines = [line.strip() for line in lines]
        return ' '.join(lines)
    except TypeError:
        return repr(g)