from invoke import task

JOB = 'mqtt_graph_bridge'
PORT = 10008
TAG = f'bang6:5000/{JOB}_x86:latest'

@task
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG} .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG}')

@task(pre=[build_image])
def shell(ctx):
    ctx.run(f'docker run --name={JOB}_shell --rm -it --cap-add SYS_PTRACE --net=host {TAG} /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --name={JOB}_local --rm -it --net=host {TAG} python3 mqtt_graph_bridge.py -v', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'supervisorctl -s http://bang:9001/ restart {JOB}_{PORT}')

@task
def program_board_over_usb(ctx):
    tag = 'esphome/esphome'
    ctx.run(f"docker run --rm -v `pwd`:/config --device=/dev/ttyUSB0 -it {tag} door.yaml run", pty=True)
# config_skylight.yaml run --no-logs

@task
def monitor_usb(ctx):
    tag = 'esphome/esphome'
    ctx.run(f"docker run --rm -v `pwd`:/config --device=/dev/ttyUSB0 -it {tag} door.yaml logs", pty=True)

@task
def tail_mqtt(ctx):
    ctx.run(f'mosquitto_sub -h bang -p 10010 -d -v -t \#')









    
