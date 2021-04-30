.. sphinx-test-reports documentation master file, created by
   sphinx-quickstart on Thu Apr 26 09:23:44 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. image:: https://img.shields.io/pypi/l/sphinx-test-reports.svg
    :target: https://pypi.python.org/pypi/sphinx-test-reports
    :alt: License
.. image:: https://img.shields.io/pypi/pyversions/sphinx-test-reports.svg
    :target: https://pypi.python.org/pypi/sphinx-test-reports
    :alt: Supported versions
.. image:: https://readthedocs.org/projects/sphinx-test-reports/badge/?version=latest
    :target: https://readthedocs.org/projects/sphinx-test-reports/
.. image:: https://travis-ci.org/useblocks/sphinx-test-reports.svg?branch=master
    :target: https://travis-ci.org/useblocks/sphinx-test-reports
    :alt: Travis-CI Build Status
.. image:: https://img.shields.io/pypi/v/sphinx-test-reports.svg
    :target: https://pypi.python.org/pypi/sphinx-test-reports
    :alt: PyPI Package latest release

Sphinx-Test-Reports
===================

``Sphinx-Test-Reports`` shows test results inside `Sphinx <http://www.sphinx-doc.org/en/master/>`_ documentations.

It provides the following features:

* :ref:`test-file`: Documents all test cases from a junit-based xml file.
* :ref:`test-suite`: Documents a specific test-suite and its test-cases.
* :ref:`test-case`: Documents a single test-case from a given file and suite.
* :ref:`test-report`: Creates a report from a test file, including tables and more for analysis.
* :ref:`test-results`: Creates a simple table of test cases inside a given file.
* :ref:`test-env`: Documents the used test-environment.
  Based on `tox-envreport <http://tox-envreport.readthedocs.io/en/latest/>`_.


Introduction
------------

A single documented test-case looks like this:

.. test-case:: test_add_source_parser
   :file: ../tests/data/pytest_sphinx_data.xml
   :suite: pytest
   :case: test_add_source_parser
   :collapse: FALSE

   Custom Message: The result is **[[copy('result')]]** with an execution time of **[[copy('time')]]**.

   Now follows automatically generated output like system-out, messages and text of the test-case.

Take a look into our :ref:`pytest example <example_pytest>` to see the complete result of all Sphinx tests
(:need_count:`'pytest_sphinx' in tags` test cases!).

The objects created by ``Sphinx-Test-Reports`` are based on
`Sphinx-Needs <https://sphinxcontrib-needs.readthedocs.io/en/latest/>`_.
So all features for filtering, sorting and showing data is supported.

As example, here is a shorten list of tests results from the Sphinx-pytest example:

.. needtable::
   :filter: 'REPORT' in tags and type == 'testcase'
   :columns: id, title, result
   :style_row: tr_[[copy('result')]]





Content
-------

.. toctree::
   :maxdepth: 2

   install
   directives/index
   configuration
   filter
   functions
   examples/index
   support
   changelog

Motivation
----------
``Sphinx-Test-Reports`` was created for an automotive project, which needs to document test results and their used
environment configuration in an human-readable format.
The goal is to provide enough information to be able to setup an identical test environment in 20+ years.

``Sphinx-Test-Reports`` is part of a software bundle, which was designed to fulfill
the parameters of the `ISO 26262 <https://en.wikipedia.org/wiki/ISO_26262>`_ standard
for safety critical software in automotive companies.

Other tools are:
`sphinx-needs <http://sphinxcontrib-needs.readthedocs.io/en/latest/>`__,
`sphinx-collections <https://sphinx-collections.readthedocs.io/en/latest/>`__ and
`tox-envreport <http://tox-envreport.readthedocs.io/en/latest/>`__.

