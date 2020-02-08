from invoke import task, Collection

import sys
sys.path.append('/my/proj/release')
from serv_tasks import serv_tasks

ns = Collection()
serv_tasks(ns, 'serv.n3', 'mqtt_to_rdf')

@ns.add_task
@task
def tail_mqtt(ctx):
    internal_mqtt_port = 10010
    ctx.run(f'mosquitto_sub -h bang -p 1883 -d -v -t \#')

@ns.add_task
@task
def setup_js(ctx):
    ctx.run('pnpm install')

@ns.add_task
@task
def build(ctx):
    ctx.run(f'pnpm run build', pty=True)

@ns.add_task
@task
def build_forever(ctx):
    ctx.run(f'pnpm run build_forever', pty=True)

@ns.add_task
@task
def test(ctx):
    ctx.run(f'pnpm run test', pty=True)

@ns.add_task
@task
def test_forever(ctx):
    ctx.run(f'pnpm run test_forever', pty=True)

