import options
import hashes
import strformat
import json

# consider https://nim-lang.org/docs/uri.html

type
  RdfNode* = ref object of RootObj
  Uri* = ref object of RdfNode
    s2: string
  Literal* = ref object of RdfNode
    value: string
    dataType: Option[Uri]

proc initUri*(s: string): Uri =
  new result
  result.s2 = s

proc cmpUri*(x, y: Uri): int =
  system.cmp(x.s2, y.s2)
  
proc `$`*(self: Uri): string =
  return self.s2

method toNt*(self: RdfNode): string {.base,gcsafe.} =
  "<<rdfnode>>"

method toNt*(self: Uri): string =
  "<" & self.s2 & ">"

proc hash*(x: RdfNode): Hash =
  hash(0)
  
func hash*(x: Uri): Hash {.inline.} =
  hash(x.s2)
  
#proc `==`*(x: Uri, y: Literal): bool = false
#proc `==`*(x: Literal, y: Uri): bool = false
#proc `==`*(x: RdfNode, y: RdfNode): bool =
#  echo "rdfnode comp"
#  true

  
proc initLiteral*(s: string): Literal =
  new result
  result.value = s
  result.dataType = none(Uri)

proc initLiteral*(s: cstring): Literal =
  new result
  result.value = $s
  result.dataType = none(Uri)

proc initLiteral*(s: string, dataType: Uri): Literal =
  new result
  result.value = s
  result.dataType = some(dataType)

# proc initLiteral*(x: int): Literal =
# proc initLiteral*(x: float): Literal =
# ...

proc hash*(x: Literal): Hash =
  hash(x.value) # maybe datatype

method toNt*(self: Literal): string =
  var dtPart: string = ""
  if isSome(self.dataType):
    let dt: Uri = self.dataType.get()
    dtPart = "^^" & dt.toNt()

  return "\"" & self.value & "\"" & dtPart


method toJsonLdObject*(self: RdfNode): JsonNode {.base,gcsafe.} =
  %* {"some": "rdfnode"}

method toJsonLdObject*(self: Uri): JsonNode =
  %* {"@id": self.s2}

method toJsonLdObject*(self: Literal): JsonNode =
  %* {"@value": $self.value}
  # and datatype and lang


