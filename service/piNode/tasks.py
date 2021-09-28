from invoke import task

JOB = 'pi_node'
PORT = 9059
TAG = f'bang5:5000/{JOB.lower()}_pi:latest'
ANSIBLE_TAG = 'raspi_io_node'

@task
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG} .')

@task
def build_image_check(ctx):
    ctx.run(f'docker build --network=host -f Dockerfile.check -t bang6:5000/pi_node_check:latest .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG}')

@task(pre=[build_image])
def shell(ctx):
    ctx.run(f'docker run --name={JOB}_shell --rm -it --cap-add SYS_PTRACE --net=host --uts=host --cap-add SYS_RAWIO --device /dev/mem  --privileged {TAG} /bin/bash', pty=True)

@task(pre=[build_image_check])
def check(ctx):
    ctx.run(f'docker run --name={JOB}_check --rm -it -v `pwd`:/opt --net=host bang6:5000/pi_node_check:latest pytype -d import-error mypkg/piNode.py', pty=True)

@task(pre=[build_image_check])
def check_shell(ctx):
    ctx.run(f'docker run --name={JOB}_check --rm -it -v `pwd`:/opt --net=host bang6:5000/pi_node_check:latest /bin/bash', pty=True)


@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --name={JOB}_local --rm -it {TAG} python ./piNode.py -v', pty=True)

@task(pre=[build_image_check])
def auto_button_test(ctx):
    ctx.run(f'docker run --name={JOB}_button --rm -it --hostname demo -v `pwd`:/opt bang6:5000/pi_node_check:latest python3 -B ./auto_button_test.py', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'sudo /my/proj/ansible/playbook -l pi -t {ANSIBLE_TAG}')

@task
def push_config(ctx):
    ctx.run(f'docker run --name={JOB}_config --rm --net=host --dns 10.2.0.1 --dns-search bigasterisk.com -v `pwd`/config:/opt/config bang6:5000/arduino_node python pushConfig.py pi/')
