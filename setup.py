#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

requires = ['Sphinx>=0.6']

setup(
    name='sphinxcontrib-needs',
    version='0.1.27',
    url='http://github.com/useblocks/sphinxcontrib-needs',
    download_url='http://pypi.python.org/pypi/sphinxcontrib-needs',
    license='BSD',
    author='team useblocks',
    author_email='info@useblocks.com',
    description='Sphinx needs extension for managing needs/requirements and specifications',
    long_description=open(os.path.join(os.path.dirname(__file__), "README.rst")).read(),
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Documentation',
        'Topic :: Utilities',
    ],
    platforms='any',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires,
    namespace_packages=['sphinxcontrib'],
)
