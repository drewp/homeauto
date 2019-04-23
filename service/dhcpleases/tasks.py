from invoke import task

JOB = 'dhcpleases'
PORT = 9073
TAG = f'bang6:5000/{JOB}_x86:latest'


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
    ctx.run(f'docker run --rm -it -p {PORT}:{PORT} --net=host -v /opt/dnsmasq:/opt/dnsmasq {TAG} python3 dhcpleases.py -v', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'sudo /my/proj/ansible/playbook -l bang -t {JOB}')
    ctx.run(f'supervisorctl -s http://bang:9001/ restart {JOB}_{PORT}')
