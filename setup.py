#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

requires = ['Sphinx<2;python_version<"3.5"',
            'Sphinx;python_version>="3.5"',
            'six',
            'matplotlib<=3.0.3.;python_version<"3.6"',
            'matplotlib;python_version>="3.6"']

setup(
    name='sphinxcontrib-needs',
    # If you raise, think about versions in conf.py and needs.py!!!
    version='0.5.2',
    url='http://github.com/useblocks/sphinxcontrib-needs',
    download_url='http://pypi.python.org/pypi/sphinxcontrib-needs',
    license='MIT',
    author='team useblocks',
    author_email='info@useblocks.com',
    description='Sphinx needs extension for managing needs/requirements and specifications',
    long_description=open(os.path.join(os.path.dirname(__file__), "README.rst")).read(),
    zip_safe=False,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Documentation',
        'Topic :: Utilities',
    ],
    platforms='any',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires,
    namespace_packages=['sphinxcontrib'],
)
