import sets
import unittest
import rdf
import rdf_nodes
import strformat

suite "rdf":
  let EX = initNamespace("http://example.com/")
  test "construct quad with uri obj":
    let q: Quad = (EX["a"], EX["b"], EX["c"], EX["d"])

  test "construct quad with string literal obj":
    let q: Quad = (EX["a"], EX["b"], initLiteral("hi"), EX["d"])

  test "construct quad with typed literal obj":
    let q: Quad = (EX["a"], EX["b"], initLiteral("hi", EX["dt"]), EX["d"])

  test "uri can be used in a set":
    let uris = toSet[Uri]([EX["a"]])
    
  test "quad can be used in a set":
    let q1 = Quad((EX["a"], EX["b"], EX["c"], EX["ctx"]))
    let quads = toSet([q1])
    
  test "uri stringify":
    require($EX["a"] == "http://example.com/a")

  test "quads to json":
    let q1 = Quad((EX["a"], EX["b"], EX["c"], EX["ctx"]))
    let q2 = Quad((EX["a"], EX["b"], EX["c2"], EX["ctx2"]))
    require(toJsonLd(toSet([q1, q2])) == """[{"@graph":[{"@id":"http://example.com/a","http://example.com/b":["http://example.com/c"]}],"@id":"http://example.com/ctx"},{"@graph":[{"@id":"http://example.com/a","http://example.com/b":["http://example.com/c2"]}],"@id":"http://example.com/ctx2"}]""")

  test "uri toNt":
    require(EX["a"].toNt() == "<http://example.com/a>")

  test "string literal toNt":
    let n = initLiteral("hi")
    require(n.toNt() == "\"hi\"")

  test "string literal with dataType toNt":
    let n = initLiteral("3.14", initUri("http://www.w3.org/2001/XMLSchema#float"))
    require(n.toNt() == "\"3.14\"^^<http://www.w3.org/2001/XMLSchema#float>")
    
    
