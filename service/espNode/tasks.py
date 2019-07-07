from invoke import task

@task
def program_board_over_usb(ctx, board):
    tag = 'esphome/esphome'
    ctx.run(f"docker run --rm -v `pwd`:/config -v /usr/share/fonts:/usr/share/fonts --device=/dev/ttyUSB1 -it {tag} {board}.yaml run", pty=True)

@task
def program_board_over_wifi(ctx, board):
    tag = 'esphome/esphome'
    ctx.run(f"docker run --rm -v `pwd`:/config -v /usr/share/fonts:/usr/share/fonts -it --net=host {tag} {board}.yaml run", pty=True)

@task
def monitor_usb(ctx, board):
    tag = 'esphome/esphome'
    ctx.run(f"docker run --rm -v `pwd`:/config --device=/dev/ttyUSB0 -it {tag} {board}.yaml logs", pty=True)
