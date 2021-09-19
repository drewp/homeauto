from time import clock_gettime
import unittest

from rdflib.term import Variable

from inference_test import N3
from rdflib import ConjunctiveGraph, Graph, Literal, Namespace, Variable

from stmt_chunk import ChunkedGraph, Chunk, applyChunky

ROOM = Namespace('http://projects.bigasterisk.com/room/')

from lhs_evaluation import functionsFor
from candidate_binding import CandidateBinding


class TestChunkedGraph(unittest.TestCase):

    def testMakesSimpleChunks(self):
        cg = ChunkedGraph(N3(':a :b :c .'), functionsFor)

        self.assertSetEqual(cg.chunksUsedByFuncs, set())
        self.assertSetEqual(cg.patternChunks, set())
        self.assertSetEqual(cg.staticChunks, set([Chunk((ROOM.a, ROOM.b, ROOM.c), subjList=None, objList=None)]))

    def testSeparatesPatternChunks(self):
        cg = ChunkedGraph(N3('?x :b :c . :a ?y :c . :a :b ?z .'), functionsFor)
        self.assertEqual(len(cg.patternChunks), 3)

    def testBoolMeansEmpty(self):
        self.assertTrue(ChunkedGraph(N3(":a :b :c ."), functionsFor))
        self.assertFalse(ChunkedGraph(N3(""), functionsFor))

    def testContains(self):
        # If I write with assertIn, there's a seemingly bogus pytype error.
        self.assert_(Chunk((ROOM.a, ROOM.b, ROOM.c)) in ChunkedGraph(N3(":a :b :c ."), functionsFor))
        self.assert_(Chunk((ROOM.a, ROOM.b, ROOM.zzz)) not in ChunkedGraph(N3(":a :b :c ."), functionsFor))

    def testNoPredicatesAppear(self):
        cg = ChunkedGraph(N3(":a :b :c ."), functionsFor)
        self.assertTrue(cg.noPredicatesAppear([ROOM.d, ROOM.e]))
        self.assertFalse(cg.noPredicatesAppear([ROOM.b, ROOM.d]))


class TestListCollection(unittest.TestCase):

    def testSubjList(self):
        cg = ChunkedGraph(N3('(:u :v) :b :c .'), functionsFor)
        expected = Chunk((None, ROOM.b, ROOM.c), subjList=[ROOM.u, ROOM.v])
        self.assertEqual(cg.staticChunks, set([expected]))

    def testObjList(self):
        cg = ChunkedGraph(N3(':a :b (:u :v) .'), functionsFor)
        expected = Chunk((ROOM.a, ROOM.b, None), objList=[ROOM.u, ROOM.v])
        self.assertSetEqual(cg.staticChunks, set([expected]))

    def testVariableInListMakesAPatternChunk(self):
        cg = ChunkedGraph(N3(':a :b (?x :v) .'), functionsFor)
        expected = Chunk((ROOM.a, ROOM.b, None), objList=[Variable('x'), ROOM.v])
        self.assertSetEqual(cg.patternChunks, set([expected]))

    def testListUsedTwice(self):
        cg = ChunkedGraph(N3('(:u :v) :b :c, :d .'), functionsFor)

        self.assertSetEqual(
            cg.staticChunks,
            set([
                Chunk((None, ROOM.b, ROOM.c), subjList=[ROOM.u, ROOM.v]),
                Chunk((None, ROOM.b, ROOM.d), subjList=[ROOM.u, ROOM.v])
            ]))

    def testUnusedListFragment(self):
        cg = ChunkedGraph(N3(':a rdf:first :b .'), functionsFor)
        self.assertFalse(cg)


class TestApplyChunky(unittest.TestCase):
    binding = CandidateBinding({Variable('x'): ROOM.xval})

    def testBoundStatementsOnly(self):
        ret = list(
            applyChunky(self.binding,
                        g=[Chunk((ROOM.a, ROOM.b, Variable('x'))),
                           Chunk((ROOM.ay, ROOM.by, Variable('y')))],
                        returnBoundStatementsOnly=True))
        self.assertEqual(ret, [Chunk((ROOM.a, ROOM.b, ROOM.xval))])

    def testAllStatements(self):
        ret = list(
            applyChunky(self.binding,
                        g=[Chunk((ROOM.a, ROOM.b, Variable('x'))),
                           Chunk((ROOM.ay, ROOM.by, Variable('y')))],
                        returnBoundStatementsOnly=False))
        self.assertCountEqual(
            ret,
            [
                Chunk((ROOM.a, ROOM.b, ROOM.xval)),  #
                Chunk((ROOM.ay, ROOM.by, Variable('y')))
            ])
