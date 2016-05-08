"""
Why?

Consider these rules:
{ :button1 :state :press . :lights :brightness 0 } => { :lights :brightness 1 }
{ :button1 :state :press . :lights :brightness 1 } => { :lights :brightness 0 }
{ :room1 :sees :motion } => { :house :sees :motion }
{ :room2 :sees :motion } => { :house :sees :motion }
{ :house :sees :motion } => { :outsideLights :brightness 1 }

Suppose we ran with these inputs:
 :lights :brightness 0 .
 :button1 :state :press .
Those will trigger the first *two* rules, since we run rules forward
until no more statements are produced.

The problem here is that (:lights :brightness ?x) is both an input
statement and an output statement, but it's the kind of output that is
not meant to cascade into more rules. A more precise way to read the
first rule is "if button1 is pressed and lights WERE at brightness 0,
then the lights SHOULD BE at brightness 1".

Can we just stop running the rules when we get the first :brightness
output and not run the second rule? Not in general. Consider the third
rule, which generates (:house :sees :motion). That output triple is
meant as an input to the last rule. There's no clear difference
between (:lights :brightness 1) and (:house :sees :motion) in this
graph. Only with external knowledge do I know that (:lights
:brightness 1) shouldn't cascade.

Possible fixes:

1. Make the :brightness predicate more clear, like
   (:lights :was_brightness 0) or (:lights :new_brightness 1). Dealing
   with multiple predicates for different "tenses" seems like a pain.

2. Put input statements in a subgraph and match them specifically in there:
     {
       :button1 :state :press . GRAPH :input { :lights :brightness 0 }
     } => {
       :lights :brightness 1
     }

   (:button1 :state :press) is allowed to match anywhere, but (:lights
   :brightness 0) must be found in the :input graph. How do you say
   this in N3? My example is half SPARQL. Also, how do you make rule
   authors remember to do this? The old mistake is still possible.

3. (current choice) RDF-reify output statements so they don't cascade,
   then recover them after the rule run is done.

     {
       :button1 :state :press . :lights :brightness 0
     } => {
       :output :statement [ :subj :lights; :pred :brightness; :obj 1 ]
     }

   This works since the output statement definitely won't trigger more
   rules that match on :lights :brightness. It's easy to recover the true
   output statement after the rules run. Like #2 above, it's still easy
   to forget to reify the output statement. We can automate the
   reification, though: given patterns like (?s :brightness ?o), we can
   rewrite the appropriate statements in implied graphs to their reified
   versions. escapeOutputStatements does this.

4. Reify input statements. Just like #3, but alter the input
   statements instead of outputs.

   This seems more expensive than #3 since there are lots of input
   statements that are given to the rules engine, including many that are
   never used in any rules, but they'd all have to get reified into 4x as
   many statements. And, even within the patterns that do appear in the
   rules, a given triple probably appears in more input graphs than
   output graphs.
"""
import unittest
from rdflib.parser import StringInputSource
from rdflib import Graph, URIRef, Namespace, BNode
from rdflib.compare import isomorphic

NS = Namespace('http://projects.bigasterisk.com/room/')

def escapeOutputStatements(graph, outputPatterns):
    """
    Rewrite
      {} => { :s :p :o } .
    to
      {} => { :output :statement [ :subj :s; :pred :p; :obj :o ] } .

    if outputPatterns contains an element matching (:s, :p, :o) with
    None as wildcards.

    Operates in-place on graph.
    """
    for s, p, o in graph:
        if isinstance(o, Graph):
            o = escapeOutputStatements(o, outputPatterns)
        variants = {(s, p, o),
                    (s, p, None),
                    (s, None, o),
                    (s, None, None),
                    (None, p, o),
                    (None, p, None),
                    (None, None, o),
                    (None, None, None)}
                    
        if not variants.isdisjoint(outputPatterns):
            graph.remove((s, p, o))
            stmt = BNode()
            graph.add((stmt, NS['subj'], s))
            graph.add((stmt, NS['pred'], p))
            graph.add((stmt, NS['obj'], o))
            graph.add((NS['output'], NS['statement'], stmt))


def unquoteOutputStatements(graph):
    """
    graph can contain structures like

    :output :statement [:subj ?s; :pred ?p; :obj ?o]

    which simply mean the statements (?s ?p ?o) are meant to be in
    the output, but they had to be quoted since they look like
    input statements and we didn't want extra input rules to fire.

    This function returns the graph of (?s ?p ?o) statements found
    on :output.

    Todo: use the standard schema for the escaping, or eliminate
    it in favor of n3 graph literals.
    """
    out = Graph()
    for qs in graph.objects(NS['output'], NS['statement']):
        out.add((graph.value(qs, NS['subj']),
                 graph.value(qs, NS['pred']),
                 graph.value(qs, NS['obj'])))
    return out


################################################################
# tests
    
def fromN3(n3):
    g = Graph(identifier=URIRef('http://example.org/graph'))
    g.parse(StringInputSource(('@prefix : %s .\n' % URIRef(NS).n3()) + n3),
            format='n3')
    return g

def impliedGraph(g):
    if len(g) != 1: raise NotImplementedError
    stmt = list(g)[0]
    return stmt[2]
    
class TestEscapeOutputStatements(unittest.TestCase):
    def testPassThrough(self):
        g = fromN3(''' { :a :b :c } => { :d :e :f } . ''')
        escapeOutputStatements(g, [])
        self.assertEqual(fromN3(''' { :a :b :c } => { :d :e :f } . '''), g)

    def testMatchCompletePattern(self):
        g = fromN3(''' { :a :b :c } => { :d :e :f } . ''')
        escapeOutputStatements(g, [(NS['d'], NS['e'], NS['f'])])
        expected = fromN3('''
          { :a :b :c } =>
          { :output :statement [ :subj :d; :pred :e; :obj :f ] } . ''')
        self.assert_(isomorphic(impliedGraph(expected), impliedGraph(g)))

    def testMatchWildcardPatternOnObject(self):
        g = fromN3(''' { :a :b :c } => { :d :e :f } . ''')
        escapeOutputStatements(g, [(NS['d'], NS['e'], None)])
        expected = fromN3('''
          { :a :b :c } =>
          { :output :statement [ :subj :d; :pred :e; :obj :f ] } . ''')
        self.assert_(isomorphic(impliedGraph(expected), impliedGraph(g)))
        
    def testWildcardAndNonMatchingStatements(self):
        g = fromN3(''' { :a :b :c } => { :d :e :f . :g :e :f . } . ''')
        escapeOutputStatements(g, [(NS['d'], NS['e'], NS['f'])])
        expected = fromN3('''
          { :a :b :c } =>
          { :output :statement [ :subj :d; :pred :e; :obj :f ] .
            :g :e :f } . ''')
        self.assert_(isomorphic(impliedGraph(expected), impliedGraph(g)))
        
    def testTwoMatchingStatements(self):
        g = fromN3(''' { :a :b :c } => { :d :e :f . :g :e :f } . ''')
        escapeOutputStatements(g, [(None, NS['e'], None)])
        expected = fromN3('''
          { :a :b :c } =>
          { :output :statement [ :subj :d; :pred :e; :obj :f ],
                               [ :subj :g; :pred :e; :obj :f ] } . ''')
        self.assert_(isomorphic(impliedGraph(expected), impliedGraph(g)))

    def testDontReplaceSourceStatements(self):
        g = fromN3(''' { :a :b :c } => { :a :b :c } . ''')
        escapeOutputStatements(g, [(NS['a'], NS['b'], NS['c'])])
        expected = fromN3('''
          { :a :b :c } =>
          { :output :statement [ :subj :a; :pred :b; :obj :c ] } . ''')
        self.assert_(isomorphic(impliedGraph(expected), impliedGraph(g)))
        
