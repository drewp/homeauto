from invoke import task

JOB = 'piNode'
PORT = 9059
TAG = f'bang6:5000/{JOB.lower()}_pi:latest'
ANSIBLE_TAG = 'raspi_io_node'

@task
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG} .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG}')

#	(cd /my/proj/homeauto/service/arduinoNode; tar czf /my/site/projects/rdfdb/more2.tgz static)

@task(pre=[build_image])
def shell(ctx):
    ctx.run(f'docker run --name={JOB}_shell --rm -it --cap-add SYS_PTRACE --net=host {TAG} /bin/bash', pty=True)


@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --name={JOB}_local --rm -it {TAG} python ./piNode.py -v', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'sudo /my/proj/ansible/playbook -l pi -t {ANSIBLE_TAG}')

@task
def push_config(ctx):
    ctx.run(f'docker run --rm --net=host -v `pwd`/config:/opt/config bang6:5000/arduino_node python pushConfig.py pi/')
