from invoke import task

JOB = 'front_door_lock'
PORT = 10011
TAG = f'bang6:5000/{JOB}_x86:latest'
ANSIBLE_TAG = 'door'

@task
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG} .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG}')

@task(pre=[build_image])
def shell(ctx):
    ctx.run(f'docker run --name={JOB}_shell --rm -it --cap-add SYS_PTRACE --net=host '
            f' -v `pwd`/../../stubs:/opt/stubs'
            f' {TAG} /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --name={JOB}_local --rm -it --net=host -v `pwd`/index.html:/opt/index.html {TAG} python3 ./front_door_lock.py -v', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'sudo /my/proj/ansible/playbook -l bang -t {ANSIBLE_TAG}')
    ctx.run(f'supervisorctl -s http://bang:9001/ restart {JOB}_{PORT}')

@task
def program_board_over_usb(ctx):
    tag = 'esphome/esphome'
    ctx.run(f"docker pull {tag}")
    ctx.run(f"docker run --rm -v `pwd`:/config --device=/dev/ttyUSB0 -it {tag} door.yaml run", pty=True)

@task
def monitor_usb(ctx):
    tag = 'esphome/esphome'
    ctx.run(f"docker run --rm -v `pwd`:/config --device=/dev/ttyUSB0 -it {tag} door.yaml logs", pty=True)

@task
def tail_mqtt(ctx):
    ctx.run(f'mosquitto_sub -h bang -p 10210 -d -v -t \#')

@task
def mqtt_force_open(ctx):
    ctx.run(f'mosquitto_pub -h bang -p 10210 -t frontdoorlock/switch/strike/command -m ON')

@task
def mqtt_force_lock(ctx):
    ctx.run(f'mosquitto_pub -h bang -p 10210 -t frontdoorlock/switch/strike/command -m OFF')
    

@task(pre=[build_image])
def mypy(ctx):
    ctx.run(f'docker run --rm -it --name={JOB}_mypy --net=host'
            f' -v `pwd`/.mypy_cache:/opt/.mypy_cache'
            f' -v `pwd`/../../stubs:/opt/stubs'
            f' -e MYPYPATH=/opt/stubs'
            f' {TAG}'
            f' /usr/local/bin/mypy -m front_door_lock', pty=True)
    
