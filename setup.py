#!/usr/bin/env python
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
        name='asyncio_amp',
        author='Jonathan Slenders',
        version='0.1',
        license='LICENSE.txt',
        url='https://github.com/jonathanslenders/asyncio-amp',

        description='PEP 3156 implementation of the AMP protocol.',
        long_description=open("README.rst").read(),
        packages=['asyncio_amp'],
        install_requires = [ 'asyncio' ],
)
