from invoke import task, Collection

import sys
sys.path.append('/my/proj/release')
from serv_tasks import serv_tasks

ns = Collection()

coll = Collection('announce')
ns.add_collection(coll)
serv_tasks(coll, 'serv.n3', 'announce')

coll = Collection('tts')
ns.add_collection(coll)
serv_tasks(ns, 'serv.n3', 'tts_server')
