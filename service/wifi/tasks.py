from invoke import task

JOB = 'wifi'
PORT = 9070
TAG = f'bang6:5000/{JOB}_x86:latest'

@task
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG} .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG}')

@task(pre=[build_image])
def shell(ctx):
    ctx.run(f'docker run --name {JOB}_shell --rm -it --cap-add SYS_PTRACE --net=host {TAG} /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --name {JOB}_local --rm -it --net=host {TAG} python3 wifi.py -v', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'supervisorctl -s http://bang:9001/ restart {JOB}_{PORT}')
