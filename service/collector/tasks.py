from invoke import task


@task(pre=[build_image])
def shell(ctx):
    ctx.run(f'docker run --rm --name={JOB}_shell -v `pwd`/.mypy_cache:/opt/.mypy_cache -v `pwd`/../../stubs:/opt/stubs -v `pwd`/sse_collector.py:/opt/sse_collector.py  --net=host {TAG_x86} /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --rm -it -p {PORT}:{PORT} --net=host --cap-add SYS_PTRACE --dns 10.2.0.1 --dns-search bigasterisk.com -v `pwd`/static:/opt/static {TAG_x86} python3 sse_collector.py -i', pty=True)
