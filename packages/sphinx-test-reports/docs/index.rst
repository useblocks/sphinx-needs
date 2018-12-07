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


Functions
---------

* Shows **test results** of *JUnit based xml reports* as table.
  JUnit exports are supported by:

  * `pytest <https://docs.pytest.org/en/latest/usage.html#creating-junitxml-format-files>`_
  * `nosetest <http://nose.readthedocs.io/en/latest/plugins/xunit.html#module-nose.plugins.xunit>`_
  * Other test frameworks (including frameworks from java and co.) support also the JUnit format.

* Shows **test environment information** from `tox-envreport <http://tox-envreport.readthedocs.io/en/latest/>`_
  based exports as table. (E.g. used operating system, python version, installed packages, ...)


.. note:: This plugin is in an early alpha phase and under heavy development.

Example
-------

Input
~~~~~

**my_data.xml**

.. literalinclude:: ../tests/data/xml_data_2.xml

**my_document.rst**

.. code-block:: rst

   My Test Results
   ===============

   .. test-results:: my_data.xml

Output
~~~~~~

.. test-results:: ../tests/data/xml_data_2.xml


Motivation
----------
``Sphinx-Test-Reports`` was created for an automotive project, which needs to document test results and their used
environment configuration in an human-readable format.
The goal is to provide enough information to be able to setup an identical test environment in 20+ years.

``Sphinx-Test-Reports`` is part of a software bundle, which was designed to fulfill
the parameters of the `ISO 26262 <https://en.wikipedia.org/wiki/ISO_26262>`_ standard
for safety critical software in automotive companies.

Other tools are: `sphinx-needs <http://sphinxcontrib-needs.readthedocs.io/en/latest/>`_
and `tox-envreport <http://tox-envreport.readthedocs.io/en/latest/>`_


Content
-------

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   directives/test_results
   directives/test_env
   changelog
