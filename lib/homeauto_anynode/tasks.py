from invoke import task

import sys
sys.path.append('/my/proj/release')
from release import local_release

@task
def release(ctx):
    local_release(ctx)
