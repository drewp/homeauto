import unittest

from rdflib import ConjunctiveGraph, Namespace, Graph
from rdflib.parser import StringInputSource

from inference import Inference

ROOM = Namespace('http://projects.bigasterisk.com/room/')


def N3(txt: str):
    g = ConjunctiveGraph()
    prefix = "@prefix : <http://example.com/> .\n"
    g.parse(StringInputSource((prefix + txt).encode('utf8')), format='n3')
    return g


def makeInferenceWithRules(n3):
    inf = Inference()
    inf.setRules(N3(n3))
    return inf


class WithGraphEqual(unittest.TestCase):

    def assertGraphEqual(self, g: Graph, expected: Graph):
        stmts1 = list(g.triples((None, None, None)))
        stmts2 = list(expected.triples((None, None, None)))
        self.assertCountEqual(stmts1, stmts2)


class TestInferenceWithoutVars(WithGraphEqual):

    def testEmitNothing(self):
        inf = makeInferenceWithRules("")
        implied = inf.infer(N3(":a :b :c ."))
        self.assertEqual(len(implied), 0)

    def testSimple(self):
        inf = makeInferenceWithRules("{ :a :b :c . } => { :a :b :new . } .")
        implied = inf.infer(N3(":a :b :c ."))
        self.assertGraphEqual(implied, N3(":a :b :new ."))

    def testTwoRounds(self):
        inf = makeInferenceWithRules("""
        { :a :b :c . } => { :a :b :new1 . } .
        { :a :b :new1 . } => { :a :b :new2 . } .
        """)

        implied = inf.infer(N3(":a :b :c ."))
        self.assertGraphEqual(implied, N3(":a :b :new1, :new2 ."))


class TestInferenceWithVars(WithGraphEqual):

    def testVarInSubject(self):
        inf = makeInferenceWithRules("{ ?x :b :c . } => { :new :stmt ?x } .")
        implied = inf.infer(N3(":a :b :c ."))
        self.assertGraphEqual(implied, N3(":new :stmt :a ."))

    def testVarInObject(self):
        inf = makeInferenceWithRules("{ :a :b ?x . } => { :new :stmt ?x } .")
        implied = inf.infer(N3(":a :b :c ."))
        self.assertGraphEqual(implied, N3(":new :stmt :c ."))

    def testVarMatchesTwice(self):
        inf = makeInferenceWithRules("{ :a :b ?x . } => { :new :stmt ?x } .")
        implied = inf.infer(N3(":a :b :c, :d ."))
        self.assertGraphEqual(implied, N3(":new :stmt :c, :d ."))

    def testTwoRulesWithVars(self):
        inf = makeInferenceWithRules("""
        { :a :b ?x . } => { :new :stmt ?x } .
        { ?y :stmt ?z . } => { :new :stmt2 ?z }
        """)
        implied = inf.infer(N3(":a :b :c ."))
        self.assertGraphEqual(implied, N3(":new :stmt :c; :stmt2 :new ."))


class TestInferenceWithMathFunctions(WithGraphEqual):

    def test1(self):
        inf = makeInferenceWithRules("{ :a :b ?x . ?x math:greaterThan 5 } => { :new :stmt ?x } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 3 .")), N3(""))
        self.assertGraphEqual(inf.infer(N3(":a :b 5 .")), N3(""))
        self.assertGraphEqual(inf.infer(N3(":a :b 6 .")), N3(":new :stmt :a ."))

class TestInferenceWithCustomFunctions(WithGraphEqual):

    def testAsFarenheit(self):
        inf = makeInferenceWithRules("{ :a :b ?x . ?x :asFarenheit ?f } => { :new :stmt ?f } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 0 .")), N3(":new :stmt -32 ."))
