from rdflib import Literal, URIRef

def render(configGraph, boards):
    nodes = {} # uri: (nodeid, nodeline)
    edges = []

    serial = [0]
    def addNode(node):
        if node not in nodes or isinstance(node, Literal):
            id = 'node%s' % serial[0]
            if isinstance(node, URIRef):
                short = configGraph.qname(node)
            else:
                short = str(node)
            nodes[node] = (
                id,
                '%s [ label="%s", shape = record, color = blue ];' % (
                id, short))
            serial[0] += 1
        else:
            id = nodes[node][0]
        return id
    def addStmt(stmt):
        ns = addNode(stmt[0])
        no = addNode(stmt[2])
        edges.append('%s -> %s [ label="%s" ];' % (
            ns, no, configGraph.qname(stmt[1])))
    for b in boards:
        for stmt in b.currentGraph():
            # color these differently from config ones
            addStmt(stmt)
    for stmt in configGraph:
        addStmt(stmt)

    nodes = '\n'.join(line for _, line in nodes.values())
    edges = '\n'.join(edges)
    return '''
    digraph {
     graph [ranksep=0.4];
    node [fontsize=8, margin=0];
    edge[weight=1.2, fontsize=8, fontcolor="gray"];
    rankdir = LR;
    charset="utf-8";
    %(nodes)s
    %(edges)s
    }
    ''' % dict(nodes=nodes, edges=edges)
