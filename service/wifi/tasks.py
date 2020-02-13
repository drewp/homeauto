from invoke import Collection
import sys
sys.path.append('/my/proj/release')
from serv_tasks import serv_tasks

ns = Collection()
serv_tasks(ns, 'serv.n3', 'wifi')
