from setuptools import setup
 
setup(
    name='mqtt_client',
    version='0.0.0',
    packages=['mqtt_client'],
    package_dir={'mqtt_client': ''},
    install_requires=['rx', 'twisted-mqtt'],
    url='https://projects.bigasterisk.com/mqtt-client/mqtt_client-0.0.0.tar.gz',
    author='Drew Perttula',
    author_email='drewp@bigasterisk.com',
)
