from setuptools import setup
 
setup(
    name='patchablegraph',
    version='0.4.0',
    packages=['patchablegraph'],
    package_dir={'patchablegraph': ''},
    install_requires=[
        'cyclone',
        'twisted',
        'rdflib-jsonld >= 0.3',
        'rdfdb @ https://projects.bigasterisk.com/rdfdb/rdfdb-0.8.0.tar.gz',
        'scales @ git+http://github.com/drewp/scales.git@448d59fb491b7631877528e7695a93553bfaaa93',
        'cycloneerr @ https://projects.bigasterisk.com/cycloneerr/cycloneerr-0.1.0.tar.gz',
        'twisted_sse @ https://projects.bigasterisk.com/twisted_sse/twisted_sse-0.3.0.tar.gz',
    ],
    url='https://projects.bigasterisk.com/patchablegraph/patchablegraph-0.4.0.tar.gz',
    author='Drew Perttula',
    author_email='drewp@bigasterisk.com',
)
