import unittest

from rdflib import BNode, Literal, Namespace

from mqtt_message import graphFromMessage

ROOM = Namespace('http://projects.bigasterisk.com/room/')
JSON = Namespace('http://bigasterisk.com/anyJson/')


class TestGraphFromMessage(unittest.TestCase):

    def testTopicOutput(self):
        graph = graphFromMessage(b'a/b/topic', b'body')
        self.assertEqual(len(graph), 9)

    def testFloatBody(self):
        graph = graphFromMessage(b'a/b/topic', b'3.3')
        self.assertEqual(list(graph.objects(None, ROOM['bodyFloat'])), [Literal(3.3)])

    def testStrBody(self):
        graph = graphFromMessage(b'a/b/topic', b'3.x')
        self.assertEqual(list(graph.objects(None, ROOM['body'])), [Literal("3.x")])

    def testJsonEmptyBody(self):
        graph = graphFromMessage(b'x', b'{}')
        [jsonRoot] = graph.objects(None, ROOM['bodyJson'])
        self.assertIsInstance(jsonRoot, BNode)

    def testJsonBody(self):
        graph = graphFromMessage(b'x', b'{"one":2}')
        [jsonRoot] = graph.objects(None, ROOM['bodyJson'])
        [(p, o)] = graph.predicate_objects(jsonRoot)
        self.assertEqual(p, JSON['one'])
        self.assertEqual(o, Literal(2))
