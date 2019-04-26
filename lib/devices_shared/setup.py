from distutils.core import setup
 
setup(
    name='devices_shared',
    version='0.1.0',
    packages=['devices_shared'],
    package_dir={'devices_shared': ''},
    requires=[
        'numpy',
        'imageio',
        'rdflib',
    ],
    url='https://projects.bigasterisk.com/devices_shared/devices_shared-0.1.0.tar.gz',
    author='Drew Perttula',
    author_email='drewp@bigasterisk.com',
)
