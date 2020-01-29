from invoke import task
JOB = 'collector'
PORT = 9072
TAG_x86 = f'bang6:5000/{JOB.lower()}_x86:latest'

ANSIBLE_TAG = 'reasoning' # sic

@task
def build_image(ctx):
    ctx.run(f'docker build --network=host -t {TAG_x86} .')

@task(pre=[build_image])
def push_image(ctx):
    ctx.run(f'docker push {TAG_x86}')

@task(pre=[build_image])
def shell(ctx):
    ctx.run(f'docker run --rm --name={JOB}_shell --cap-add SYS_PTRACE --dns 10.2.0.1 --dns-search bigasterisk.com -it --cap-add SYS_PTRACE -v `pwd`/.mypy_cache:/opt/.mypy_cache -v `pwd`/../../stubs:/opt/stubs -v `pwd`/sse_collector.py:/opt/sse_collector.py  --net=host {TAG_x86} /bin/bash', pty=True)

@task(pre=[build_image])
def local_run(ctx):
    ctx.run(f'docker run --rm -it -p {PORT}:{PORT} --net=host --cap-add SYS_PTRACE --dns 10.2.0.1 --dns-search bigasterisk.com -v `pwd`/static:/opt/static {TAG_x86} python3 sse_collector.py -i', pty=True)

#local_run_strace: build_image
#	docker run --rm -it -p ${PORT}:${PORT} \ --name=$(JOB)_local \ --net=host \ --cap-add SYS_PTRACE \ ${TAG} \ strace -f -tts 200 python3 /mnt/sse_collector.py -v

#local_run_pyspy: build_image
#	docker run --rm -it -p ${PORT}:${PORT} \ --name=$(JOB)_local \ --net=host \ --cap-add SYS_PTRACE \ ${TAG} \ py-spy -- python3 sse_collector.py

#typecheck: build_image
#	docker run --rm -it -p ${PORT}:${PORT} \ --name=$(JOB)_mypy \ --net=host \ -v `pwd`/.mypy_cache:/opt/.mypy_cache \ ${TAG} \
#           /usr/local/bin/mypy -m sse_collector -m export_to_influxdb -m logsetup -m patchablegraph -m patchsource -m rdfdb.patch

#redeploy: push_image
#	supervisorctl restart sse_collector_9072

@task(pre=[push_image])
def redeploy(ctx):
    ctx.run(f'supervisorctl -s http://bang:9001/ restart sse_{JOB}_{PORT}')
