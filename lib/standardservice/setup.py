from setuptools import setup
 
setup(
    name='standardservice',
    version='0.6.0',
    packages=['standardservice'],
    package_dir={'standardservice': ''},
    install_requires=[
        'psutil',
        'twisted',
        'scales', # use git+http://github.com/drewp/scales.git@master#egg=scales
    ],
    url='https://projects.bigasterisk.com/standardservice/standardservice-0.6.0.tar.gz',
    author='Drew Perttula',
    author_email='drewp@bigasterisk.com',
)
