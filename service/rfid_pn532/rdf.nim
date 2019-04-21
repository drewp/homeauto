import algorithm
import hashes
import json
import sequtils
import sets
import strformat
import strutils

import rdf_nodes

type Namespace* = object of RootObj
  prefix: string
  
proc initNamespace*(prefix: string): Namespace =
  result.prefix = prefix

proc `[]`*(self: Namespace, tail: string): Uri =
  initUri(self.prefix & tail)


type Quad* = tuple[s: Uri, p: Uri, o: RdfNode, g: Uri]
     
proc toJsonLd*(quads: HashSet[Quad]): string =
  var graphs: HashSet[Uri] = toSet[Uri]([])
  graphs.init()
  for q in quads:
    graphs.incl(q.g)
  var graphUris = toSeq[Uri](graphs.items)
  graphUris.sort(cmpUri)
  var graphJson = newJArray()
  for g in graphUris:
    var quadsInGraph: seq[JsonNode]
    for q in quads:
      if q.g == g:
        quadsInGraph.add(%* {"@id": $q.s, $q.p: [toJsonLdObject(q.o)]})
      
    graphJson.add(%* {"@graph": quadsInGraph, "@id": $g})
  $graphJson
    

proc hash*(x: Quad): Hash =
  hash(1)

type Patch* = object of RootObj
  addQuads*: HashSet[Quad]
  delQuads*: HashSet[Quad]

proc toJson*(self: Patch): string =
  $ %* {"patch" : {"adds": self.addQuads.toJsonLd(),
                   "deletes": self.delQuads.toJsonLd()}}
  
  
type Graph* = object of RootObj
  stmts*: HashSet[Quad]

proc len*(self: Graph): int = len(self.stmts)
  
proc initGraph*(): Graph =
  result.stmts.init()

proc applyPatch*(self: var Graph, p: Patch) =
  self.stmts.excl(p.delQuads)
  self.stmts.incl(p.addQuads)

proc toNquads*(self: var Graph): string =
  var lines: seq[string] = @[]
  for q in self.stmts:
    lines.add(&"{q.s.toNt()} {q.p.toNt()} {q.o.toNt()} {q.g.toNt()} .\n")
  return lines.join("")

proc toNtriples*(stmts: openArray[Quad]): string =
  var lines: seq[string] = @[]
  for q in stmts:
    lines.add(&"{q.s.toNt()} {q.p.toNt()} {q.o.toNt()} .\n")
  return lines.join("")

