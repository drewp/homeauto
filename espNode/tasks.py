from invoke import task

tag = 'esphome/esphome:dev'

@task
def pull_esphome(ctx):
    ctx.run(f"docker pull {tag}")

@task
def program_board_over_usb(ctx, board):
    ctx.run(f"docker run --rm -v `pwd`:/config -v /usr/share/fonts:/usr/share/fonts --device=/dev/ttyUSB0 -it {tag} {board}.yaml run", pty=True)

@task
def program_board_over_wifi(ctx, board):
    ctx.run(f"docker run --rm -v `pwd`:/config -v /usr/share/fonts:/usr/share/fonts -it --net=host {tag} {board}.yaml run", pty=True)

@task
def monitor_usb(ctx, board):
    ctx.run(f"docker run --rm -v `pwd`:/config --device=/dev/ttyUSB0 -it {tag} {board}.yaml logs", pty=True)

# device up?
#  nmap -Pn -p 3232,6053 10.2.0.21
