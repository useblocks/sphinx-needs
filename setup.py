#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

requires = ['Sphinx', 'six']

setup(
    name='sphinxcontrib-needs',
    # If you raise, think about versions in conf.py and needs.py!!!
    version='0.2.5',
    url='http://github.com/useblocks/sphinxcontrib-needs',
    download_url='http://pypi.python.org/pypi/sphinxcontrib-needs',
    license='MIT',
    author='team useblocks',
    author_email='info@useblocks.com',
    description='Sphinx needs extension for managing needs/requirements and specifications',
    long_description=open(os.path.join(os.path.dirname(__file__), "README.rst")).read(),
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Documentation',
        'Topic :: Utilities',
    ],
    platforms='any',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires,
    namespace_packages=['sphinxcontrib'],
)
