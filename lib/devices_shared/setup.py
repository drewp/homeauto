from setuptools import setup
 
setup(
    name='devices_shared',
    version='0.5.0',
    packages=['devices_shared'],
    package_dir={'devices_shared': ''},
    install_requires=[
        'numpy',
        'imageio',
        'rdflib',
    ],
    url='https://projects.bigasterisk.com/devices-shared/devices_shared-0.5.0.tar.gz',
    author='Drew Perttula',
    author_email='drewp@bigasterisk.com',
)
