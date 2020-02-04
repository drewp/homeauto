from invoke import task

import sys
sys.path.append('/my/proj/release')
from release import local_release

@task
def release(ctx):
    local_release(ctx)

@task
def browser_test_build(ctx):
    ctx.run(f'docker build --network=host  -t bang:5000/patchable_graph_browser_test .')

@task(pre=[browser_test_build])
def browser_test(ctx):
    ctx.run(f'docker run '
            f'--name patchable_graph_browser_test '
            f'--rm -it '
            f'--net=host '
            f'-v `pwd`:/opt '
            f'bang:5000/patchable_graph_browser_test '
            f'/bin/bash'  #f'python3 browser_test.py',
            pty=True)
