RDF graph that accepts patches and serves them over HTTP (with a SSE protocol).

Example:

```
from patchablegraph import PatchableGraph

masterGraph = PatchableGraph()

```

Then, you call `masterGraph.patch`, etc to edit the
graph. `rdfdb.grapheditapi.GraphEditApi` is mixed in, so you can
use
[higher-level functions](https://bigasterisk.com/darcs/?r=rdfdb;a=headblob;f=/rdfdb/grapheditapi.py) from
there, such as patchObject.

Web serving:

``` from patchablegraph import CycloneGraphHandler,
CycloneGraphEventsHandler

reactor.listenTCP(9059, cyclone.web.Application([
    ...
    (r"/graph", CycloneGraphHandler, {'masterGraph': masterGraph}),
    (r"/graph/events", CycloneGraphEventsHandler, {'masterGraph': masterGraph}),
    ...
```

