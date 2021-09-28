from invoke import Collection, task

@task
def program_board_over_usb(ctx):
    tag = 'esphome/esphome'
    ctx.run(f"docker pull {tag}")
    ctx.run(f"docker run --rm -v `pwd`:/config --device=/dev/ttyUSB0 -it {tag} door.yaml run", pty=True)

@task
def monitor_usb(ctx):
    tag = 'esphome/esphome'
    ctx.run(f"docker run --rm -v `pwd`:/config --device=/dev/ttyUSB0 -it {tag} door.yaml logs", pty=True)

@task
def tail_mqtt(ctx):
    ctx.run(f'mosquitto_sub -h bang -p 10210 -d -v -t \#')

@task
def mqtt_force_open(ctx):
    ctx.run(f'mosquitto_pub -h bang -p 10210 -t frontdoorlock/switch/strike/command -m ON')

@task
def mqtt_force_lock(ctx):
    ctx.run(f'mosquitto_pub -h bang -p 10210 -t frontdoorlock/switch/strike/command -m OFF')
    
