from invoke import task

JOB='environment'
PORT=9075

TAG=f'bang6:5000/{JOB}_x86:latest'



@task
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG} .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG}')

@task
def shell(ctx):
    ctx.run(f'docker run --rm -it --cap-add SYS_PTRACE  -v `pwd`:/opt/homeauto_store --dns 10.2.0.1 --dns-search bigasterisk.com --net=host {TAG}  /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --rm -it -p {PORT}:{PORT}  -v `pwd`:/opt/homeauto_store --dns 10.2.0.1 --dns-search bigasterisk.com --net=host {TAG} python3 {JOB}.py -v', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'supervisorctl -s http://bang:9001/ restart envgraph_{PORT}')
