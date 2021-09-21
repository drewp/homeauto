"""rdflib patches for prettier debug outut"""

import itertools

import rdflib
import rdflib.plugins.parsers.notation3
import rdflib.term
from rdflib import BNode

ROOM = rdflib.Namespace('http://projects.bigasterisk.com/room/')


def patchSlimReprs():
    """From: rdflib.term.URIRef('foo')
         To: U('foo')
    """

    def ur(self):
        clsName = "U" if self.__class__ is rdflib.term.URIRef else self.__class__.__name__
        s = super(rdflib.term.URIRef, self).__str__()
        if s.startswith(str(ROOM)):
            s = ':' + s[len(ROOM):]
        return """%s(%s)""" % (clsName, s)

    rdflib.term.URIRef.__repr__ = ur

    def br(self):
        clsName = "BNode" if self.__class__ is rdflib.term.BNode else self.__class__.__name__
        return """%s(%s)""" % (clsName, super(rdflib.term.BNode, self).__repr__())

    rdflib.term.BNode.__repr__ = br

    def vr(self):
        clsName = "V" if self.__class__ is rdflib.term.Variable else self.__class__.__name__
        return """%s(%s)""" % (clsName, '?' + super(rdflib.term.Variable, self).__str__())

    rdflib.term.Variable.__repr__ = vr


def patchBnodeCounter():
    """From: rdflib.terms.BNode('ne7bb4a51624993acdf51cc5d4e8add30e1' 
         To: BNode('f-6-1')
    """
    serial = itertools.count()

    def n(cls, value=None, _sn_gen='', _prefix='') -> BNode:
        if value is None:
            value = 'N-%s' % next(serial)
        return rdflib.term.Identifier.__new__(cls, value)

    rdflib.term.BNode.__new__ = n

    def newBlankNode(self, uri=None, why=None):
        if uri is None:
            self.counter += 1
            bn = BNode('f-%s-%s' % (self.number, self.counter))
        else:
            bn = BNode(uri.split('#').pop().replace('_', 'b'))
        return bn

    rdflib.plugins.parsers.notation3.Formula.newBlankNode = newBlankNode
