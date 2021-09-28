from invoke import task

tag = 'esphome/esphome:dev'
esphome = f'docker run --rm -v `pwd`:/config -v /usr/share/fonts:/usr/share/fonts -it {tag}'
esphomeUsb = esphome.replace('--rm', '--rm --device=/dev/ttyUSB0')
# on dash for lcd code for theater display:
#tag = 'esphome_dev'
#esphome = '/home/drewp/Downloads/esphome/env/bin/esphome'

@task
def get_dev_esphome(ctx):
    ctx.run(f'docker build -t esphome_dev -f docker/Dockerfile https://github.com/MasterTim17/esphome.git#dev')

@task
def pull_esphome(ctx):
    ctx.run(f"docker pull {tag}")

@task
def program_board_over_usb(ctx, board):
    board = board.replace('.yaml', '')
    print('connect gnd, 3v3, rx/tx per https://randomnerdtutorials.com/esp32-cam-video-streaming-web-server-camera-home-assistant/, ')
    print('rts to reset (if possible), dtr to gpio0 per https://github.com/espressif/esptool/wiki/ESP32-Boot-Mode-Selection#automatic-bootloader')
    ctx.run(f"{esphomeUsb} run {board}.yaml --device=/dev/ttyUSB0", pty=True)

@task
def program_board_over_wifi(ctx, board):
    board = board.replace('.yaml', '')
    ctx.run(f"{esphome} {board}.yaml run", pty=True)

@task
def monitor_usb(ctx, board):
    board = board.replace('.yaml', '')
    ctx.run(f"{esphomeUsb} logs {board}.yaml --device=/dev/ttyUSB0", pty=True)

# device up?
#  nmap -Pn -p 3232,6053 10.2.0.21
