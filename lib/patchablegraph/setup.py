from setuptools import setup
 
setup(
    name='patchablegraph',
    version='0.8.0',
    packages=['patchablegraph'],
    package_dir={'patchablegraph': ''},
    install_requires=[
        'cyclone',
        'twisted',
        'rdflib-jsonld >= 0.3',
        'rdfdb >= 0.8.0',
        'scales @ git+http://github.com/drewp/scales.git@448d59fb491b7631877528e7695a93553bfaaa93',
        'cycloneerr',
        'twisted_sse >= 0.3.0',
    ],
    url='https://projects.bigasterisk.com/patchablegraph/patchablegraph-0.8.0.tar.gz',
    author='Drew Perttula',
    author_email='drewp@bigasterisk.com',
)
