from invoke import task

JOB = 'powerEagle'
PORT = 10016
TAG = f'bang6:5000/{JOB.lower()}_x86:latest'


@task
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG} .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG}')

@task(pre=[build_image])
def shell(ctx):
    ctx.run(f'docker run --rm -it --cap-add SYS_PTRACE --net=host {TAG} /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --rm -it -p {PORT}:{PORT} -v /etc/resolv.conf:/etc/resolv.conf --net=host {TAG} python3 reader.py -v', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'sudo /my/proj/ansible/playbook -l bang -t {JOB}')
    ctx.run(f'supervisorctl -s http://bang:9001/ restart {JOB}_{PORT}')
