from invoke import Collection, task
import sys
sys.path.append('/my/proj/release')
from serv_tasks import serv_tasks

ns = Collection()
serv_tasks(ns, 'serv.n3', 'reasoning')

@ns.add_task
@task(pre=[ns['build']])
def local_run_mock(ctx):
    ctx.run(f'docker run --name reasoning_local_run_mock --rm -it -p 9071:9071 -v `pwd`:/opt --dns 10.2.0.1 --dns-search bigasterisk.com --net=host bang6:5000/reasoning:latest python3 reasoning.py -iro --mockoutput', pty=True)

@ns.add_task
@task(pre=[ns['build']])
def pytype(ctx):
    ctx.run(f'docker run '
            f'--name reasoning_pytype '
            f'--rm -it '
            f'-v `pwd`:/opt '
            f'--dns 10.2.0.1 '
            f'--dns-search bigasterisk.com '
            f'--net=host bang6:5000/reasoning:latest '
            f'pytype --pythonpath /usr/local/lib/python3.6/dist-packages:. '
            f'--jobs 4 '
            f'actions.py '
            f'escapeoutputstatements.py '
            f'graphop.py '
            f'httpputoutputs.py '
            f'inference.py '
            f'inputgraph.py '
            f'private_ipv6_addresses.py '
            f'rdflibtrig.py '
            f'reasoning.py', pty=True)
