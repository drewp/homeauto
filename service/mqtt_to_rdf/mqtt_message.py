import json
import uuid

from rdflib import RDF, URIRef, BNode, Graph, Literal, Namespace
from rdflib.collection import Collection

ROOM = Namespace('http://projects.bigasterisk.com/room/')
JSON = Namespace('http://bigasterisk.com/anyJson/')


def graphFromMessage(topic: bytes, body: bytes):
    graph = Graph()
    message = URIRef(f'{uuid.uuid1().urn}')

    graph.add((message, RDF.type, ROOM['MqttMessage']))

    topicSegments = BNode()
    graph.add((message, ROOM['topic'], topicSegments))
    Collection(graph, topicSegments, map(Literal, topic.decode('ascii').split('/')))

    bodyStr = body.decode('utf8')
    graph.add((message, ROOM['body'], Literal(bodyStr)))
    try:
        graph.add((message, ROOM['bodyFloat'], Literal(float(bodyStr))))
    except ValueError:
        pass
    _maybeAddJson(graph, message, bodyStr)
    return graph


def _maybeAddJson(graph, message, bodyStr):
    if not bodyStr.startswith('{'):
        return
    try:
        doc = json.loads(bodyStr)
    except ValueError:
        return
    print(f'got {doc=}')
    jsonRoot = BNode()
    graph.add((message, ROOM['bodyJson'], jsonRoot))
    for k, v in doc.items():
        graph.add((jsonRoot, JSON[k], Literal(v)))
