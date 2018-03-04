from __future__ import division

from twisted.internet import reactor
from twisted.internet.task import react
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.python.filepath import FilePath

import txaioetcd
etcd = txaioetcd.Client(reactor, u'http://bang6:2379')

@inlineCallbacks
def main(*a):
    prefix = b'arduino/'
    existing = set(row.key for row in
                   (yield etcd.get(txaioetcd.KeySet(prefix, prefix=True))).kvs)
    written = set()
    root = FilePath('config')
    for f in root.walk():
        if f.isfile() and f.path.endswith('.n3'):
            n3 = f.getContent()
            key = prefix + b'/'.join(f.segmentsFrom(root))
            yield etcd.set(key, n3)
            written.add(key)
            print 'wrote %s' % key
    for k in existing - written:
        yield etcd.delete(k)
        print 'removed %s' % k

react(main)
