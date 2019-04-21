from __future__ import division
import sys
import etcd3

from twisted.python.filepath import FilePath

etcd = etcd3.client(host='bang6', port=9022)

prefix, = sys.argv[1:]

def main():
    existing = set(md.key for v, md in etcd.get_prefix(prefix))
    written = set()
    root = FilePath('config')
    print 'reading at %s' % root
    for f in root.walk():
        if f.isfile() and f.path.endswith('.n3'):
            n3 = f.getContent()
            key = prefix + b'/'.join(f.segmentsFrom(root))
            etcd.put(key, n3)
            written.add(key)
            print 'wrote %s' % key
    for k in existing - written:
        etcd.delete(k)
        print 'removed %s' % k

main()
