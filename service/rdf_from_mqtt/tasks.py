from invoke import task, Collection

import sys
sys.path.append('/my/proj/release')
from serv_tasks import serv_tasks

ns = Collection()
serv_tasks(ns, 'serv.n3', 'rdf_from_mqtt')

@ns.add_task
@task
def tail_mqtt(ctx):
    internal_mqtt_port = 10010
    ctx.run(f'mosquitto_sub -h bang -p 1883 -d -v -t \#')
