import datetime, os, inspect
from dateutil.tz import tzlocal
from rdflib import Graph, Namespace, Literal
DCTERMS = Namespace("http://purl.org/dc/terms/")

class StateGraph(object):
    """
    helper to create a graph with some of the current state of the world
    """
    def __init__(self, ctx):
        """
        note that we put the time of the __init__ call into the graph
        as its dcterms:modified time.
        """
        self.g = Graph()
        self.ctx = ctx

        try:
            requestingFile = inspect.stack()[1][1]
            self.g.add((ctx, DCTERMS['creator'], 
                        Literal(os.path.abspath(requestingFile))))
        except IndexError:
            pass
        self.g.add((ctx, DCTERMS['modified'],
               Literal(datetime.datetime.now(tzlocal()))))

    def add(self, *args, **kw):
        self.g.add(*args, **kw)

    def ntLines(self):
        nt = self.g.serialize(format='nt')
        # this canonical order is just for debugging, so the lines are
        # stable when you refresh the file repeatedly
        return sorted(filter(None, nt.splitlines()))
        
    def asTrig(self):
        return "%s {\n%s\n}\n" % (self.ctx.n3(), '\n'.join(self.ntLines()))

    def asJsonLd(self):
        return self.g.serialize(format='json-ld')

    def asAccepted(self, acceptHeader):
        if acceptHeader == 'application/nquads':
            return 'application/nquads', '\n'.join(
                line.strip().rstrip('.') + '%s .' % self.ctx.n3()
                for line in self.ntLines())
        else:
            return 'application/x-trig', self.asTrig()
    
