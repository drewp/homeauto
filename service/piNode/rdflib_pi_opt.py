import rdflib.plugins.memory


def patchRandid():
    """
    I'm concerned urandom is slow on raspberry pi, and I'm adding to
    graphs a lot. Unclear what the ordered return values might do to
    the balancing of the graph.
    """
    _id_serial = [1000]
    def randid():
        _id_serial[0] += 1
        return _id_serial[0]
    rdflib.plugins.memory.randid = randid
