from invoke import Collection, task
import sys
sys.path.append('/my/proj/release')
from serv_tasks import serv_tasks

ns = Collection()
serv_tasks(ns, 'serv.n3', 'rdf_to_mqtt')

# leftover frontdoor setup I think
@ns.add_task
@task
def program_board_over_usb(ctx):
    tag = 'esphome/esphome'
    ctx.run(f"docker run --rm -v `pwd`:/config --device=/dev/ttyUSB0 -it {tag} door.yaml run", pty=True)
# config_skylight.yaml run --no-logs

@ns.add_task
@task
def monitor_usb(ctx):
    tag = 'esphome/esphome'
    ctx.run(f"docker run --rm -v `pwd`:/config --device=/dev/ttyUSB0 -it {tag} door.yaml logs", pty=True)

@ns.add_task
@task
def tail_mqtt(ctx):
    ctx.run(f'mosquitto_sub -h bang -p 10010 -d -v -t \#')
