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
    ctx.run(f'docker run --name={JOB}_shell --rm -it --cap-add SYS_PTRACE --net=host {TAG} /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --name={JOB}_local --rm -it --net=host -v `pwd`/index.html:/opt/index.html {TAG} python3 ./front_door_lock.py -v', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'sudo /my/proj/ansible/playbook -l bang -t {ANSIBLE_TAG}')
    ctx.run(f'supervisorctl -s http://bang:9001/ restart {JOB}_{PORT}')
