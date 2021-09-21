"""
also see https://github.com/w3c/N3/tree/master/tests/N3Tests
"""
import unittest
from decimal import Decimal
from typing import cast

from rdflib import ConjunctiveGraph, Graph, Literal, Namespace
from rdflib.parser import StringInputSource

from inference import Inference
from rdflib_debug_patches import patchBnodeCounter, patchSlimReprs

patchSlimReprs()
patchBnodeCounter()

EX = Namespace('http://example.com/')
ROOM = Namespace('http://projects.bigasterisk.com/room/')


def N3(txt: str):
    g = ConjunctiveGraph()
    prefix = """
@prefix : <http://projects.bigasterisk.com/room/> .
@prefix ex: <http://example.com/> .
@prefix room: <http://projects.bigasterisk.com/room/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
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


class TestNonRuleStatements(WithGraphEqual):

    def test(self):
        inf = makeInferenceWithRules(":d :e :f . { :a :b :c . } => { :a :b :new . } .")
        self.assertCountEqual(inf.nonRuleStatements(), [(ROOM.d, ROOM.e, ROOM.f)])


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


class TestBnodeAliasingSetup(WithGraphEqual):

    def setUp(self):
        self.inf = makeInferenceWithRules("""
          {
            ?var0 :a ?x; :b ?y  .
          } => {
            :xVar :value ?x .
            :yVar :value ?y .
          } .
          """)

    def assertResult(self, actual):
        self.assertGraphEqual(actual, N3("""
          :xVar :value :x0, :x1 .
          :yVar :value :y0, :y1 .
        """))

    def testMatchesDistinctStatements(self):
        implied = self.inf.infer(N3("""
          :stmt0 :a :x0; :b :y0 .
          :stmt1 :a :x1; :b :y1 .
        """))
        self.assertResult(implied)

    def testMatchesDistinctBnodes(self):
        implied = self.inf.infer(N3("""
          [ :a :x0; :b :y0 ] .
          [ :a :x1; :b :y1 ] .
        """))
        self.assertResult(implied)


class TestBnodeGenerating(WithGraphEqual):

    def testRuleBnodeMakesNewBnode(self):
        inf = makeInferenceWithRules("{ [ :a :b ] . } => { [ :c :d ] } .")
        implied = inf.infer(N3("[ :a :b ] ."))
        ruleNode = list(inf.rules[0].rhsGraph)[0]
        stmt0Node = list(implied)[0][0]
        self.assertNotEqual(ruleNode, stmt0Node)

    def testRuleBnodeMakesNewBnodesEachTime(self):
        inf = makeInferenceWithRules("{ [ :a ?x ] . } => { [ :c :d ] } .")
        implied = inf.infer(N3("[ :a :b, :e ] ."))
        ruleNode = list(inf.rules[0].rhsGraph)[0]
        stmt0Node = list(implied)[0][0]
        stmt1Node = list(implied)[1][0]

        self.assertNotEqual(ruleNode, stmt0Node)
        self.assertNotEqual(ruleNode, stmt1Node)
        self.assertNotEqual(stmt0Node, stmt1Node)


class TestSelfFulfillingRule(WithGraphEqual):

    def test1(self):
        inf = makeInferenceWithRules("{ } => { :new :stmt :x } .")
        self.assertGraphEqual(inf.infer(N3("")), N3(":new :stmt :x ."))
        self.assertGraphEqual(inf.infer(N3(":any :any :any .")), N3(":new :stmt :x ."))

    # def test2(self):
    #     inf = makeInferenceWithRules("{ (2) math:sum ?x } => { :new :stmt ?x } .")
    #     self.assertGraphEqual(inf.infer(N3("")), N3(":new :stmt 2 ."))

    # @unittest.skip("too hard for now")
    # def test3(self):
    #     inf = makeInferenceWithRules("{ :a :b :c . :a :b ?x . } => { :new :stmt ?x } .")
    #     self.assertGraphEqual(inf.infer(N3("")), N3(":new :stmt :c ."))


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
        inf = makeInferenceWithRules("{ :a :b ?x . (?x) math:sum ?y } => { :new :stmt ?y } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 3 .")), N3(":new :stmt 3 ."))

    def test2Operands(self):
        inf = makeInferenceWithRules("{ :a :b ?x . (?x 1) math:sum ?y } => { :new :stmt ?y } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 3 .")), N3(":new :stmt 4 ."))

    def test3Operands(self):
        inf = makeInferenceWithRules("{ :a :b ?x . (2 ?x 2) math:sum ?y } => { :new :stmt ?y } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 2 .")), N3(":new :stmt 6 ."))

    # def test0Operands(self):
    #     inf = makeInferenceWithRules("{ :a :b ?x . () math:sum ?y } => { :new :stmt ?y } .")
    #     self.assertGraphEqual(inf.infer(N3(":a :b 2 .")), N3(":new :stmt 0 ."))


class TestInferenceWithCustomFunctions(WithGraphEqual):

    def testAsFarenheit(self):
        inf = makeInferenceWithRules("{ :a :b ?x . ?x room:asFarenheit ?f } => { :new :stmt ?f } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 12 .")), N3(":new :stmt 53.6 ."))

    def testChildResource(self):
        inf = makeInferenceWithRules("{ :a :b ?x . (:c ?x) room:childResource ?y .} => { :new :stmt ?y  } .")
        self.assertGraphEqual(inf.infer(N3(':a :b "foo" .')), N3(":new :stmt <http://projects.bigasterisk.com/room/c/foo> ."))

    def testChildResourceSegmentQuoting(self):
        inf = makeInferenceWithRules("{ :a :b ?x . (:c ?x) room:childResource ?y .} => { :new :stmt ?y  } .")
        self.assertGraphEqual(inf.infer(N3(':a :b "b / w -> #." .')),
                              N3(":new :stmt <http://projects.bigasterisk.com/room/c/b%20%2F%20w%20-%3E%20%23.> ."))


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
        self.assertIn((ROOM['frontDoorLockStatus'], ROOM['connectedStatus'], ROOM['Online']), out)

    def testTopicIsList(self):
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
        self.assertIn((ROOM['frontDoorLockStatus'], ROOM['connectedStatus'], ROOM['Online']), out)

    def testPerformance0(self):
        inf = makeInferenceWithRules('''
            {
              ?msg a :MqttMessage;
                :topic :topic1;
                :bodyFloat ?valueC .
              ?valueC math:greaterThan -999 .
              ?valueC room:asFarenheit ?valueF .
            } => {
              :airQualityIndoorTemperature :temperatureF ?valueF .
            } .
        ''')
        out = inf.infer(
            N3('''
            <urn:uuid:c6e1d92c-0ee1-11ec-bdbd-2a42c4691e9a> a :MqttMessage ;
                :body "23.9" ;
                :bodyFloat 2.39e+01 ;
                :topic :topic1 .
            '''))

        vlit = cast(Literal, out.value(ROOM['airQualityIndoorTemperature'], ROOM['temperatureF']))
        valueF = cast(Decimal, vlit.toPython())
        self.assertAlmostEqual(float(valueF), 75.02)

    def testPerformance1(self):
        inf = makeInferenceWithRules('''
            {
              ?msg a :MqttMessage;
                :topic ( "air_quality_indoor" "sensor" "bme280_temperature" "state" );
                :bodyFloat ?valueC .
              ?valueC math:greaterThan -999 .
              ?valueC room:asFarenheit ?valueF .
            } => {
              :airQualityIndoorTemperature :temperatureF ?valueF .
            } .
        ''')
        out = inf.infer(
            N3('''
            <urn:uuid:c6e1d92c-0ee1-11ec-bdbd-2a42c4691e9a> a :MqttMessage ;
                :body "23.9" ;
                :bodyFloat 2.39e+01 ;
                :topic ( "air_quality_indoor" "sensor" "bme280_temperature" "state" ) .
        '''))
        vlit = cast(Literal, out.value(ROOM['airQualityIndoorTemperature'], ROOM['temperatureF']))
        valueF = cast(Decimal, vlit.toPython())
        self.assertAlmostEqual(float(valueF), 75.02)

    def testEmitBnodes(self):
        inf = makeInferenceWithRules('''
            { ?s a :AirQualitySensor; :label ?name . } => {
                [ a :MqttStatementSource;
                :mqttTopic (?name "sensor" "bme280_temperature" "state") ] .
            } .
        ''')
        out = inf.infer(N3('''
            :airQualityOutdoor a :AirQualitySensor; :label "air_quality_outdoor" .
        '''))
        out.bind('', ROOM)
        out.bind('ex', EX)
        self.assertEqual(
            out.serialize(format='n3'), b'''\
@prefix : <http://projects.bigasterisk.com/room/> .
@prefix ex: <http://example.com/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xml: <http://www.w3.org/XML/1998/namespace> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

[] a :MqttStatementSource ;
    :mqttTopic ( "air_quality_outdoor" "sensor" "bme280_temperature" "state" ) .

''')


class TestListPerformance(WithGraphEqual):

    def testList1(self):
        inf = makeInferenceWithRules("{ :a :b (:e0) . } => { :new :stmt :here } .")
        implied = inf.infer(N3(":a :b (:e0) ."))
        self.assertGraphEqual(implied, N3(":new :stmt :here ."))

    def testList2(self):
        inf = makeInferenceWithRules("{ :a :b (:e0 :e1) . } => { :new :stmt :here } .")
        implied = inf.infer(N3(":a :b (:e0 :e1) ."))
        self.assertGraphEqual(implied, N3(":new :stmt :here ."))

    def testList3(self):
        inf = makeInferenceWithRules("{ :a :b (:e0 :e1 :e2) . } => { :new :stmt :here } .")
        implied = inf.infer(N3(":a :b (:e0 :e1 :e2) ."))
        self.assertGraphEqual(implied, N3(":new :stmt :here ."))

    # def testList4(self):
    #     inf = makeInferenceWithRules("{ :a :b (:e0 :e1 :e2 :e3) . } => { :new :stmt :here } .")
    #     implied = inf.infer(N3(":a :b (:e0 :e1 :e2 :e3) ."))
    #     self.assertGraphEqual(implied, N3(":new :stmt :here ."))


# def fakeStats():
#     return defaultdict(lambda: 0)

# class TestLhsFindCandidateBindings(WithGraphEqual):

#     def testBnodeMatchesStmt(self):
#         l = Lhs(N3("[] :a :b ."))
#         ws = ReadOnlyGraphAggregate([N3("[] :a :b .")])
#         cands = list(l.findCandidateBindings(ws, fakeStats()))
#         self.assertEqual(len(cands), 1)

#     def testVarMatchesStmt(self):
#         l = Lhs(N3("?x :a :b ."))
#         ws = ReadOnlyGraphAggregate([N3("[] :a :b .")])
#         cands = list(l.findCandidateBindings(ws, fakeStats()))
#         self.assertEqual(len(cands), 1)

#     def testListsOnlyMatchEachOther(self):
#         l = Lhs(N3(":a :b (:e0 :e1) ."))
#         ws = ReadOnlyGraphAggregate([N3(":a :b (:e0 :e1) .")])
#         stats = fakeStats()
#         cands = list(l.findCandidateBindings(ws, stats))
#         self.assertLess(stats['permCountFailingVerify'], 20)