"""
also see https://github.com/w3c/N3/tree/master/tests/N3Tests
"""
import unittest

from rdflib import RDF, BNode, ConjunctiveGraph, Graph, Literal, Namespace
from rdflib.parser import StringInputSource

from inference import Inference, parseList
from rdflib_debug_patches import patchBnodeCounter, patchSlimReprs

patchSlimReprs()
patchBnodeCounter()

EX = Namespace('http://example.com/')
ROOM = Namespace('http://projects.bigasterisk.com/room/')


def N3(txt: str):
    g = ConjunctiveGraph()
    prefix = """
@prefix : <http://example.com/> .
@prefix room: <http://projects.bigasterisk.com/room/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
"""
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

    def testTwoRulesApplyIndependently(self):
        inf = makeInferenceWithRules("""
            { :a :b ?x . } => { :new :stmt ?x . } .
            { :d :e ?y . } => { :new :stmt2 ?y . } .
            """)
        implied = inf.infer(N3(":a :b :c ."))
        self.assertGraphEqual(implied, N3("""
            :new :stmt :c .
            """))
        implied = inf.infer(N3(":a :b :c . :d :e :f ."))
        self.assertGraphEqual(implied, N3("""
            :new :stmt :c .
            :new :stmt2 :f .
            """))

    def testOneRuleActivatesAnother(self):
        inf = makeInferenceWithRules("""
            { :a :b ?x . } => { :new :stmt ?x . } .
            { ?y :stmt ?z . } => { :new :stmt2 ?y . } .
            """)
        implied = inf.infer(N3(":a :b :c ."))
        self.assertGraphEqual(implied, N3("""
            :new :stmt :c .
            :new :stmt2 :new .
            """))

    def testVarLinksTwoStatements(self):
        inf = makeInferenceWithRules("{ :a :b ?x . :d :e ?x } => { :new :stmt ?x } .")
        implied = inf.infer(N3(":a :b :c  ."))
        self.assertGraphEqual(implied, N3(""))
        implied = inf.infer(N3(":a :b :c . :d :e :f ."))
        self.assertGraphEqual(implied, N3(""))
        implied = inf.infer(N3(":a :b :c . :d :e :c ."))
        self.assertGraphEqual(implied, N3(":new :stmt :c ."))

    def testRuleMatchesStaticStatement(self):
        inf = makeInferenceWithRules("{ :a :b ?x . :a :b :c . } => { :new :stmt ?x } .")
        implied = inf.infer(N3(":a :b :c  ."))
        self.assertGraphEqual(implied, N3(":new :stmt :c ."))


class TestBnodeMatching(WithGraphEqual):

    def testRuleBnodeBindsToInputBnode(self):
        inf = makeInferenceWithRules("{ [ :a :b ] . } => { :new :stmt :here } .")
        implied = inf.infer(N3("[ :a :b ] ."))
        self.assertGraphEqual(implied, N3(":new :stmt :here ."))

    def testRuleVarBindsToInputBNode(self):
        inf = makeInferenceWithRules("{ ?z :a :b  . } => { :new :stmt :here } .")
        implied = inf.infer(N3("[] :a :b ."))
        self.assertGraphEqual(implied, N3(":new :stmt :here ."))


class TestSelfFulfillingRule(WithGraphEqual):

    def test1(self):
        inf = makeInferenceWithRules("{ } => { :new :stmt :x } .")
        self.assertGraphEqual(inf.infer(N3("")), N3(":new :stmt :x ."))
        self.assertGraphEqual(inf.infer(N3(":any :any :any .")), N3(":new :stmt :x ."))

    def test2(self):
        inf = makeInferenceWithRules("{ (2) math:sum ?x } => { :new :stmt ?x } .")
        self.assertGraphEqual(inf.infer(N3("")), N3(":new :stmt 2 ."))


class TestInferenceWithMathFunctions(WithGraphEqual):

    def testBoolFilter(self):
        inf = makeInferenceWithRules("{ :a :b ?x . ?x math:greaterThan 5 } => { :new :stmt ?x } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 3 .")), N3(""))
        self.assertGraphEqual(inf.infer(N3(":a :b 5 .")), N3(""))
        self.assertGraphEqual(inf.infer(N3(":a :b 6 .")), N3(":new :stmt 6 ."))

    def testNonFiringMathRule(self):
        inf = makeInferenceWithRules("{ :a :b ?x . (?x 1) math:sum ?y } => { :new :stmt ?y } .")
        self.assertGraphEqual(inf.infer(N3("")), N3(""))

    def testStatementGeneratingRule(self):
        inf = makeInferenceWithRules("{ :a :b ?x . (?x 1) math:sum ?y } => { :new :stmt ?y } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 3 .")), N3(":new :stmt 4 ."))

    def test3Operands(self):
        inf = makeInferenceWithRules("{ :a :b ?x . (2 ?x 2) math:sum ?y } => { :new :stmt ?y } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 2 .")), N3(":new :stmt 6 ."))

    def test0Operands(self):
        inf = makeInferenceWithRules("{ :a :b ?x . () math:sum ?y } => { :new :stmt ?y } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 2 .")), N3(":new :stmt 0 ."))


class TestInferenceWithCustomFunctions(WithGraphEqual):

    def testAsFarenheit(self):
        inf = makeInferenceWithRules("{ :a :b ?x . ?x room:asFarenheit ?f } => { :new :stmt ?f } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 12 .")), N3(":new :stmt 53.6 ."))


class TestParseList(unittest.TestCase):

    def test0Elements(self):
        g = N3(":a :b () .")
        bn = g.value(EX['a'], EX['b'])
        elems, used = parseList(g, bn)
        self.assertEqual(elems, [])
        self.assertFalse(used)

    def test1Element(self):
        g = N3(":a :b (0) .")
        bn = g.value(EX['a'], EX['b'])
        elems, used = parseList(g, bn)
        self.assertEqual(elems, [Literal(0)])
        used = sorted(used)
        self.assertEqual(used, [
            (bn, RDF.first, Literal(0)),
            (bn, RDF.rest, RDF.nil),
        ])


class TestUseCases(WithGraphEqual):

    def testSimpleTopic(self):
        inf = makeInferenceWithRules('''
{ ?msg :body "online" . } => { ?msg :onlineTerm :Online . } .
 { ?msg :body "offline" . } => { ?msg :onlineTerm :Offline . } .

{
  ?msg a :MqttMessage ;
     :topic :foo;
     :onlineTerm ?onlineness . } => {
  :frontDoorLockStatus :connectedStatus ?onlineness .
} .
        ''')

        out = inf.infer(N3('[] a :MqttMessage ; :body "online" ; :topic :foo .'))
        self.assertIn((EX['frontDoorLockStatus'], EX['connectedStatus'], EX['Online']), out)

    def testTopicIsListhg(self):
        inf = makeInferenceWithRules('''
{ ?msg :body "online" . } => { ?msg :onlineTerm :Online . } .
{ ?msg :body "offline" . } => { ?msg :onlineTerm :Offline . } .

{
  ?msg a :MqttMessage ;
     :topic ( "frontdoorlock" "status" );
     :onlineTerm ?onlineness . } => {
  :frontDoorLockStatus :connectedStatus ?onlineness .
} .
        ''')

        out = inf.infer(N3('[] a :MqttMessage ; :body "online" ; :topic ( "frontdoorlock" "status" ) .'))
        self.assertIn((EX['frontDoorLockStatus'], EX['connectedStatus'], EX['Online']), out)
