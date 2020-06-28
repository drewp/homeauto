from invoke import task, Collection
import sys
sys.path.append('/my/proj/release')
from serv_tasks import serv_tasks

ns = Collection()
serv_tasks(ns, 'serv.n3', 'xidle_dash')

if 0:

    TAG_x86 = f'bang6:5000/{JOB.lower()}_x86:latest'
    TAG_pi = f'bang6:5000/{JOB.lower()}_pi:latest'
    ANSIBLE_TAG = 'homeauto_xidle'

    @task
    def build_image_x86(ctx):
        ctx.run(f'docker build --network=host -t {TAG_x86} .')
    @task
    def build_image_pi(ctx):
        ctx.run(f'docker build --file Dockerfile.pi --network=host -t {TAG_pi} .')

    @task(pre=[build_image_x86])
    def push_image_x86(ctx):
        ctx.run(f'docker push {TAG_x86}')
    @task(pre=[build_image_pi])
    def push_image_pi(ctx):
        ctx.run(f'docker push {TAG_pi}')

    @task(pre=[build_image_x86])
    def shell(ctx):
        ctx.run(f'docker run --rm -it --cap-add SYS_PTRACE -v /tmp/.X11-unix/:/tmp/.X11-unix/ -v /home/drewp/.Xauthority:/root/.Xauthority --net=host {TAG_x86} /bin/bash', pty=True)

    @task(pre=[build_image_x86])
    def local_run(ctx):
        ctx.run(f'docker run --rm -it -v /tmp/.X11-unix/:/tmp/.X11-unix/ -v /home/drewp/.Xauthority:/root/.Xauthority -p {PORT}:{PORT} -v /etc/resolv.conf:/etc/resolv.conf --net=host {TAG_x86} python3 xidle.py -v', pty=True)

    @task(pre=[push_image_x86, push_image_pi])
    def redeploy(ctx):
        ctx.run(f'sudo /my/proj/ansible/playbook -t {ANSIBLE_TAG}')
        #ctx.run(f'supervisorctl -s http://bang:9001/ restart {JOB}_{PORT}')
