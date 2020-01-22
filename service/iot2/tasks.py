from invoke import task
from pathlib import Path

@task
def nim_install(ctx):
    if Path('nim-1.0.4/bin/nim').exists():
        return
    ctx.run(f'curl https://nim-lang.org/download/nim-1.0.4-linux_x64.tar.xz | xz -dc | tar x')

@task
def py_install(ctx):
    if Path('env/bin/python').exists():
        return
    ctx.run(f'mkdir -p env')
    ctx.run(f'virtualenv -p /usr/bin/python3.7 env')

@task(pre=[py_install])
def py_deps(ctx):
    pip_install_ran = Path('env/lib/python3.7/site-packages/wheel').stat().st_mtime
    requirements = Path('requirements.txt').stat().st_mtime
    if pip_install_ran > requirements:
        return
    ctx.run(f'env/bin/pip install --quiet --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt')

@task(pre=[nim_install])
def nim_deps(ctx):
    pkgs = ['nimpy-0.1.0']
    if all(Path(f'~/.nimble/pkgs/{pkg}').expanduser().exists() for pkg in pkgs):
        return
    plain_names = ' '.join(p.split('-')[0] for p in pkgs)
    ctx.run(f'nim-1.0.4/bin/nimble install {plain_names}', pty=True)


@task(pre=[nim_install])
def nim_build_x86(ctx):
    ctx.run(f'nim-1.0.4/bin/nim c --out:iot2_linux_x86 iot2_linux.nim', pty=True)

@task
def arm_cross_compiler_install(ctx):
    ctx.run(f'sudo apt install -y crossbuild-essential-armhf', pty=True)

@task(pre=[nim_install])
def nim_build_arm(ctx):
    ctx.run(f'nim-1.0.4/bin/nim c --cpu:arm --out:iot2_linux_arm iot2_linux.nim', pty=True)

@task(pre=[py_deps, nim_build_x86])
def local_run(ctx):
    ctx.run(f'./iot2_linux_x86')


# pack this into docker for pushing to Pi

# apt install -y sshfs
# sshfs drewp@10.2.0.110:/my/proj/homeauto/service/iot2 /mnt
# cd /mnt
# ./iot2_linux_arm
