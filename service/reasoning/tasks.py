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
    ctx.run(f'docker run --name {JOB}_shell --rm -it --cap-add SYS_PTRACE -v `pwd`:/mnt --dns 10.2.0.1 --dns-search bigasterisk.com --net=host {TAG}  /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --name {JOB}_local --rm -it '
            f'-p {PORT}:{PORT} '
            f'-v `pwd`:/mnt '
            f'-v `pwd`/index.html:/opt/index.html '
            f'--dns 10.2.0.1 --dns-search bigasterisk.com '
            f'--net=host '
            f'{TAG} '
            f'python /mnt/{JOB}.py -iro', pty=True)

@task(pre=[build_image])
def local_run_mock(ctx):
    ctx.run(f'docker run --name {JOB}_local_run_mock --rm -it -p {PORT}:{PORT} -v `pwd`:/mnt  --dns 10.2.0.1 --dns-search bigasterisk.com --net=host {TAG} python /mnt/{JOB}.py -iro --mockoutput', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'supervisorctl -s http://bang:9001/ restart {JOB}_{PORT}')
