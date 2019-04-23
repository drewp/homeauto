from distutils.core import setup
 
setup(
    name='patchablegraph',
    version='0.0.0',
    packages=['patchablegraph'],
    package_dir={'patchablegraph': ''},
    requires=[
        'cyclone',
        'twisted',
        'rdflib-jsonld>=0.3',
        'git+http://github.com/drewp/scales.git@448d59fb491b7631877528e7695a93553bfaaa93#egg=scales',
        
        'https://projects.bigasterisk.com/rdfdb/rdfdb-0.8.0.tar.gz',
        'https://projects.bigasterisk.com/cycloneerr/cycloneerr-0.1.0.tar.gz',
        'https://projects.bigasterisk.com/twisted_sse/twisted_sse-0.3.0.tar.gz',
    ],
    url='https://projects.bigasterisk.com/patchablegraph/patchablegraph-0.0.0.tar.gz',
    author='Drew Perttula',
    author_email='drewp@bigasterisk.com',
)
