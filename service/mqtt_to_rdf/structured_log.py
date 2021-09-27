import re
from pathlib import Path
from typing import List, Optional, Union, cast

import simple_html.render
from rdflib import Graph
from rdflib.term import Node
from simple_html.nodes import (SafeString, body, div, head, hr, html, span,
                               style, table, td, tr)

from candidate_binding import CandidateBinding
from inference_types import Triple
from stmt_chunk import Chunk, ChunkedGraph

CSS = SafeString('''
@import url('https://fonts.googleapis.com/css2?family=Oxygen+Mono&display=swap');

* {
    font-family: 'Oxygen Mono', monospace;
    font-size: 10px;
}
.arrow {
    font-size: 350%;
    vertical-align: middle;
}
table {
    border-collapse: collapse;
}
td {
    vertical-align: top;
    border: 1px solid gray;
    padding: 2px;
}
.consider.isNew-False {
    opacity: .3;
}
.iteration {
   font-size: 150%;
    padding: 20px 0;
    background: #c7dec7;
}
.timetospin {
    font-size: 150%;
    margin-top: 20 px ;
    padding: 10 px 0;
    background: #86a886;
}
.looper {
    background: #e2e2e2;
}
.alignedWorkingSetChunk tr:nth-child(even) {
    background: #bddcbd;
}
.alignedWorkingSetChunk tr:nth-child(odd) {
    background: hsl(120deg 31% 72%);
}
.highlight, .alignedWorkingSetChunk tr.highlight  {
    background: #ffffd6;
    outline: 1px solid #d2d200;
    padding: 2px;
    line-height: 17px;
}
.node { padding: 0 2px; }
.URIRef { background: #e0b3b3; }
.Literal { background: #eecc95 }
.Variable { background: #aaaae8; }
.BNode { background: orange; }
.say {
    white-space: pre-wrap;
}
.say.now.past.end {
    color: #b82c08;
}
.say.restarts {
    color: #51600f;
}
.say.advance.start {
    margin-top: 5px;
}
.say.finished {
    border-bottom: 1px solid gray;
   display: inline-block;
   margin-bottom: 8px;
}
''')


class StructuredLog:
    workingSet: Graph

    def __init__(self, output: Path):
        self.output = output
        self.steps = []

    def say(self, line):
        classes = ['say'] + [c for c in re.split(r'\s+|\W|(\d+)', line) if c]
        cssList = ' '.join(classes)
        self.steps.append(div.attrs(('class', cssList))(line))

    def startIteration(self, num: int):
        self.steps.extend([hr(), div.attrs(('class', 'iteration'))(f"iteration {num}")])

    def rule(self, workingSet: Graph, i: int, rule):
        self.steps.append(htmlGraph('working set', self.workingSet))
        self.steps.append(f"try rule {i}")
        self.steps.append(htmlRule(rule))

    def foundBinding(self, bound):
        self.steps.append(div('foundBinding', htmlBinding(bound.binding)))

    def looperConsider(self, looper, newBinding, fullBinding, isNew):
        self.steps.append(
            table.attrs(('class', f'consider isNew-{isNew}'))(tr(
                td(htmlChunkLooper(looper, showBindings=False)),
                td(div('newBinding', htmlBinding(newBinding))),
                td(div('fullBinding', htmlBinding(fullBinding))),
                td(f'{isNew=}'),
            )))

    def odometer(self, chunkStack):
        self.steps.append(
            table(
                tr(*[
                    td(
                        table.attrs(('class', 'looper'))(
                            tr(
                                td(htmlChunkLooper(looper, showBindings=False)),  #
                                td(div('newBinding'),
                                   htmlBinding(looper.localBinding()) if not looper.pastEnd() else '(pastEnd)'),  #
                                td(div('fullBinding'),
                                   htmlBinding(looper.currentBinding()) if not looper.pastEnd() else ''),  #
                            ))) for looper in chunkStack
                ])))

    def render(self):

        with open(self.output, 'w') as out:
            out.write(simple_html.render.render(html(head(style(CSS)), body(div(*self.steps)))))


def htmlRule(r):
    return table(tr(td(htmlGraph('lhsGraph', r.lhsGraph)), td(htmlGraph('rhsGraph', r.rhsGraph))))


def htmlGraph(label: str, g: Graph):
    return div(label, table(*[htmlStmtRow(s) for s in sorted(g)]))


def htmlStmtRow(s: Triple):
    return tr(td(htmlTerm(s[0])), td(htmlTerm(s[1])), td(htmlTerm(s[2])))


def htmlTerm(t: Union[Node, List[Node]]):
    if isinstance(t, list):
        return span('( ', *[htmlTerm(x) for x in t], ')')
    return span.attrs(('class', 'node ' + t.__class__.__name__))(repr(t))


def htmlBinding(b: CandidateBinding):
    return table(*[tr(td(htmlTerm(k)), td(htmlTerm(v))) for k, v in sorted(b.binding.items())])


def htmlChunkLooper(looper, showBindings=True):
    alignedMatches = []
    for i, arc in enumerate(looper._alignedMatches):
        hi = arc.workingSetChunk == looper.currentSourceChunk
        alignedMatches.append(
            tr.attrs(('class', 'highlight' if hi else ''))(
                td(span.attrs(('class', 'arrow'))('➢' if hi else ''), str(i)),  #
                td(htmlChunk(arc.workingSetChunk))))
    return table(
        tr(
            td(div(repr(looper)), div(f"prev = {looper.prev}")),
            td(
                div('lhsChunk'),
                htmlChunk(looper.lhsChunk),  #
                div('alignedMatches'),
                table.attrs(('class', 'alignedWorkingSetChunk'))(*alignedMatches)  #
            ),
            td('localBinding', htmlBinding(looper.localBinding())) if showBindings else '',
            td('currentBinding', htmlBinding(looper.currentBinding())) if showBindings else '',
        ))


def htmlChunkedGraph(g: ChunkedGraph, highlightChunk: Optional[Chunk] = None):
    return table(
        tr(td('staticChunks'), td(*[div(htmlChunk(ch, ch == highlightChunk)) for ch in sorted(g.staticChunks)])),
        tr(td('patternChunks'), td(*[div(htmlChunk(ch, ch == highlightChunk)) for ch in sorted(g.patternChunks)])),
        tr(td('chunksUsedByFuncs'), td(*[div(htmlChunk(ch, ch == highlightChunk)) for ch in sorted(g.chunksUsedByFuncs)])),
    )


def htmlChunk(ch: Chunk, highlight=False):
    return span.attrs(('class', 'highlight' if highlight else ''))(
        'subj=',
        htmlTerm(ch.primary[0] if ch.primary[0] is not None else cast(List[Node], ch.subjList)),  #
        ' pred=',
        htmlTerm(ch.predicate),  #
        ' obj=',
        htmlTerm(ch.primary[2] if ch.primary[2] is not None else cast(List[Node], ch.objList)))
