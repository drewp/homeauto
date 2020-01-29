from invoke import task
from pathlib import Path

PY_ENV = f'build/py'
NIM_ENV = f'build/nim'
NIM_BIN = f'{NIM_ENV}/bin'
PY_SITE_PACKAGES = f'{PY_ENV}/lib/python3.7/site-packages'
SOME_PY_DEP = Path(f'{PY_SITE_PACKAGES}/standardservice')

@task
def nim_install(ctx):
    if Path(f'{NIM_BIN}/nim').exists():
        return
    ctx.run(f'curl https://nim-lang.org/download/nim-1.0.4-linux_x64.tar.xz | '
            f'xz -dc | '
            f'tar --extract --strip-components=1 --one-top-level={NIM_ENV}')

@task
def py_install(ctx):
    if Path(f'{PY_ENV}/bin/python').exists():
        return
    ctx.run(f'mkdir -p {PY_ENV}')
    ctx.run(f'virtualenv -p /usr/bin/python3.7 {PY_ENV}')
    # now .../wheel is newer than requirements.txt

@task(pre=[py_install])
def py_deps(ctx):
    pip_install_ever_ran = SOME_PY_DEP.exists()
    pip_install_last_ran = Path(f'{PY_SITE_PACKAGES}/wheel').stat().st_mtime
    requirements = Path('requirements.txt').stat().st_mtime
    if pip_install_ever_ran and pip_install_last_ran > requirements:
        return
    ctx.run(f'{PY_ENV}/bin/pip install '
            #f'--quiet '
            f'--index-url https://projects.bigasterisk.com/ '
            f'--extra-index-url https://pypi.org/simple '
            f'-r requirements.txt')

@task(pre=[nim_install])
def nim_deps(ctx):
    pkgs = [('nimpy', 'nimpy-0.1.0'),
            ('https://github.com/avsej/capnp.nim.git', 'capnp-0.0.3'),
            ]
    if all(Path(f'~/.nimble/pkgs/{pkg[1]}').expanduser().exists() for pkg in pkgs):
        return
    plain_names = ' '.join(p[0] for p in pkgs)
    print('todo: on initial install, this may need to be run a few times')
    ctx.run(f'{NIM_BIN}/nimble install -y {plain_names}',
            pty=True, env={'PATH': f'/usr/bin:{NIM_BIN}'})
    ctx.run(f'ln -s ~/.nimble/bin/capnpc ~/.nimble/bin/capnpc-nim')


@task(pre=[nim_deps])
def nim_build_x86(ctx):
    ctx.run(f'{NIM_BIN}/nim compile '
            f'--out:build/iot2_linux_x86 '
            f'iot2_linux.nim',
            pty=True)

@task
def arm_cross_compiler_install(ctx):
    if Path('/usr/share/crossbuild-essential-armhf/list').exists():
        return
    ctx.run(f'sudo apt install -y crossbuild-essential-armhf', pty=True)

@task(pre=[arm_cross_compiler_install, nim_install])
def nim_build_arm(ctx):
    ctx.run(f'{NIM_BIN}/nim compile '
            f'--cpu:arm '
            f'--out:build/iot2_linux_arm '
            f'iot2_linux.nim',
            pty=True)

@task(pre=[py_deps, nim_build_x86])
def local_run(ctx):
    ctx.run(f'build/iot2_linux_x86')

@task
def nim_build_esp32(ctx):
    ctx.run(f'{NIM_BIN}/nim compile '
            f'--cpu:arm '
            f'--os:standalone '
            #f'--deadCodeElim:on '
            # --gc:refc|v2|markAndSweep|boehm|go|none|regions
            f'--gc:stack '
            f'--compileOnly:on '
            f'--noMain '
            f'--nimcache:build/nimcache '
            f'--embedsrc:on '
            f'--verbosity:3 '
            #f'-d:release '
            f'iot2_esp32.nim')
    ctx.run(f'')

@task
def install_nim_capnp(ctx):
    ctx.run(f'git clone git@github.com:drewp/capnp.nim.git build/capnp.nim')
    ctx.run(f'cd build/capnp.nim; ./build.sh')
    ctx.run(f'cd build/capnp.nim; bin/nim c capnp/capnpc.nim')

@task
def messages_build_nim(ctx):
    ctx.run(f'capnp compile -o ./build/capnp.nim/capnp/capnpc messages.capnp > build/messages.nim')


# pack this into docker for pushing to Pi

# apt install -y sshfs
# sshfs drewp@10.2.0.110:/my/proj/homeauto/service/iot2 /mnt
# cd /mnt
# ./iot2_linux_arm
