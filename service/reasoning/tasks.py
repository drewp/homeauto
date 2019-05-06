from invoke import task

JOB='reasoning'
PORT=9071

TAG=f'bang6:5000/{JOB}_x86:latest'

@task
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG} .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG}')

@task
def shell(ctx):
    ctx.run(f'docker run --rm -it --cap-add SYS_PTRACE --net=host {TAG}  /bin/bash')

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --rm -it -p {PORT}:{PORT} -v `pwd`:/mnt --net=host {TAG} python /mnt/{JOB}.py -iro', pty=True)

@task(pre=[build_image])
def redeploy(ctx): 
    ctx.run(f'supervisorctl -s http://bang:9001/ restart {JOB}_{PORT}')
