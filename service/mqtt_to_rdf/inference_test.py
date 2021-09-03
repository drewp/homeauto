"""
also see https://github.com/w3c/N3/tree/master/tests/N3Tests
"""
import unittest
import itertools
from rdflib import ConjunctiveGraph, Namespace, Graph, BNode
from rdflib.parser import StringInputSource

from inference import Inference


def patchSlimReprs():
    import rdflib.term

    def ur(self):
        clsName = "U" if self.__class__ is rdflib.term.URIRef else self.__class__.__name__
        return """%s(%s)""" % (clsName, super(rdflib.term.URIRef, self).__repr__())

    rdflib.term.URIRef.__repr__ = ur

    def br(self):
        clsName = "BNode" if self.__class__ is rdflib.term.BNode else self.__class__.__name__
        return """%s(%s)""" % (clsName, super(rdflib.term.BNode, self).__repr__())

    rdflib.term.BNode.__repr__ = br

    def vr(self):
        clsName = "V" if self.__class__ is rdflib.term.Variable else self.__class__.__name__
        return """%s(%s)""" % (clsName, super(rdflib.term.Variable, self).__repr__())

    rdflib.term.Variable.__repr__ = vr


patchSlimReprs()


def patchBnodeCounter():
    import rdflib.term
    serial = itertools.count()

    def n(cls, value=None, _sn_gen='', _prefix='') -> BNode:
        if value is None:
            value = 'N-%s' % next(serial)
        return rdflib.term.Identifier.__new__(cls, value)

    rdflib.term.BNode.__new__ = n

    import rdflib.plugins.parsers.notation3

    def newBlankNode(self, uri=None, why=None):
        if uri is None:
            self.counter += 1
            bn = BNode('f-%s-%s' % (self.number, self.counter))
        else:
            bn = BNode(uri.split('#').pop().replace('_', 'b'))
        return bn

    rdflib.plugins.parsers.notation3.Formula.newBlankNode = newBlankNode


patchBnodeCounter()

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

    def testStatementGeneratingRule(self):
        inf = makeInferenceWithRules("{ :a :b ?x . (?x 1) math:sum ?y } => { :new :stmt ?y } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 3 .")), N3(":new :stmt 4 ."))

    def test3Operands(self):
        inf = makeInferenceWithRules("{ :a :b ?x . (2 ?x 2) math:sum ?y } => { :new :stmt ?y } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 2 .")), N3(":new :stmt 6 ."))


class TestInferenceWithCustomFunctions(WithGraphEqual):

    def testAsFarenheit(self):
        inf = makeInferenceWithRules("{ :a :b ?x . ?x room:asFarenheit ?f } => { :new :stmt ?f } .")
        self.assertGraphEqual(inf.infer(N3(":a :b 12 .")), N3(":new :stmt 53.6 ."))
