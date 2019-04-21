import sets
import hashes

type
  RdfNode* = object of RootObj
  Uri* = object of RdfNode
    s2: string

proc initUri*(s: string): Uri =
  result.s2 = s
  
proc hash*(x: Uri): Hash =
  hash(x.s2)


  
let uris = setOfUris([initUri("x")])
