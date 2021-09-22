import unittest

from rdflib import Namespace, Variable

from candidate_binding import CandidateBinding
from inference_test import N3
from lhs_evaluation import functionsFor
from stmt_chunk import AlignedRuleChunk, Chunk, ChunkedGraph, applyChunky

ROOM = Namespace('http://projects.bigasterisk.com/room/')


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

    def testAllStatements(self):
        rule0 = Chunk((ROOM.a, Variable('pred'), Variable('x')))
        rule1 = Chunk((ROOM.a, Variable('pred'), Variable('x')))
        ret = list(
            applyChunky(self.binding,
                        g=[
                           AlignedRuleChunk(ruleChunk=rule0, workingSetChunk=Chunk((ROOM.a, ROOM.b, ROOM.xval))),
                           AlignedRuleChunk(ruleChunk=rule1, workingSetChunk=Chunk((ROOM.a, ROOM.b, ROOM.yval))),
                        ]))
        self.assertCountEqual(
            ret,
            [
                AlignedRuleChunk(ruleChunk=Chunk((ROOM.a, Variable('pred'), ROOM.xval)), workingSetChunk=Chunk((ROOM.a, ROOM.b, ROOM.xval)))
            ])
