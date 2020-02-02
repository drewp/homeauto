from setuptools import setup

setup(
    name='export_to_influxdb',
    version='0.2.0',
    packages=['export_to_influxdb'],
    package_dir={'export_to_influxdb': ''},
    install_requires=[
        'influxdb >= 3.0.0',
        'scales',
    ],
    url='https://projects.bigasterisk.com/export-to-influxdb/export_to_influxdb-0.2.0.tar.gz',
    author='Drew Perttula',
    author_email='drewp@bigasterisk.com',
)
