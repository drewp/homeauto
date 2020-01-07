from invoke import task

JOB = 'wifi'
PORT = 9070
TAG = f'bang6:5000/{JOB}_x86:latest'


@task
def build(ctx):
    ctx.run(f'npm run build', pty=True)
    
@task(pre=[build])
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG} .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG}')

@task(pre=[build_image])
def shell(ctx):
    ctx.run(f'docker run --name {JOB}_shell --rm -it --cap-add SYS_PTRACE --net=host {TAG} /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --name {JOB}_local --rm -it --net=host -v `pwd`:/opt {TAG} python3 wifi.py -v', pty=True)

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'supervisorctl -s http://bang:9001/ restart {JOB}_{PORT}')


# one time:
#   yarn policies set-version v2
# and for vscode:
#   yarn pnpify --sdk
#   then pick the pnp one on statusbar.

#yarn run webpack-cli --config webpack.config.js --mode production
