# encoding: utf-8

from distribute_setup import use_setuptools
use_setuptools()
from setuptools import setup, find_packages

setup(
    name='badpubs',
    entry_points={'console_scripts': ['badpubs=badpubs:main']},
    install_requires=['distribute', 'rdflib<=2.4', 'lxml'],
    packages=find_packages('src'),
    package_dir={'': 'src'},
)
