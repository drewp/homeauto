from invoke import task

JOB = 'arduinoNode'
PORT = 9059
TAG = f'bang6:5000/{JOB.lower()}:latest'
ANSIBLE_TAG = JOB

@task
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG} .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG}')

@task(pre=[build_image])
def shell(ctx):
    ctx.run(f'docker run --name={JOB}_shell --rm -it --cap-add SYS_PTRACE --net=host --device=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A900cepU-if00-port0  -v `pwd`/config:/opt/config  {TAG} /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --name={JOB}_local --rm -it -p 9059:9059 --device=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A900cepU-if00-port0 --net=host   --dns 10.2.0.1 --dns-search bigasterisk.com {TAG} python ./arduinoNode.py -v', pty=True)

@task
def push_config(ctx):
    ctx.run(f'docker run --rm --net=host --dns 10.2.0.1 --dns-search bigasterisk.com -v `pwd`/config:/opt/config bang6:5000/arduino_node python pushConfig.py arduino/')

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'sudo /my/proj/ansible/playbook -l bang -t {ANSIBLE_TAG}')

@task
def lightsout(ctx):
    ctx.run(rf'curl http://bang:9059/output\?s\=http://projects.bigasterisk.com/room/speakersStrips\&p\=http://projects.bigasterisk.com/room/x -XPUT -v -d 199')

@task
def lightstest(ctx):
    ctx.run(rf'curl http://bang:9059/output\?s\=http://projects.bigasterisk.com/room/speakersStrips\&p\=http://projects.bigasterisk.com/room/x -XPUT -v -d 100; sleep 3; curl http://bang:9059/output\?s\=http://projects.bigasterisk.com/room/speakersStrips\&p\=http://projects.bigasterisk.com/room/x -XPUT -v -d 199')
