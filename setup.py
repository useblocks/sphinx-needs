#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

long_desc = '''
This package contains the needs Sphinx extension.

It allows the definition of needs/requirements, the listing of defined needs in lists and the reference of defined
needs in doc strings of implementation code or tests.

A need is described by the following attributes:

 * id: unique identifier
 * need: Short description of the need
 * status: A status of the need, like open, in discussion, implemented (optional)
 * tags: tags for the need, like 'important', 'easy', ... . Can be used as filter option in needlist directive.
 * show: If False, need is not printed/shown. Default is True

This extension provides the following directives:

 * *need*: Define a single need
 * *needfocused: Can contain/update  additional information for a need (Helpful, to reuse needs in different project
   contexts)
 * *needlist*: Shows a list of defined needs. Can be filtered by name, status, category
 * *needref*: Defines a reference to a defined need, e.g. to link to the implementation or test case of the need.

'''

requires = ['Sphinx>=0.6']

setup(
    name='sphinxcontrib-needs',
    version='0.1',
    url='http://github.com/useblocks/sphinxcontrib-needs',
    download_url='http://pypi.python.org/pypi/sphinxcontrib-needs',
    license='BSD',
    author='team useblocks',
    author_email='info@useblocks.com',
    description='Sphinx "needs" extension',
    long_description=long_desc,
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