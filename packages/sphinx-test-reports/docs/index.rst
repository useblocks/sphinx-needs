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

Sphinx-Test-Reports shows test results inside sphinx documentations.


Functions
---------

* Shows **test results** of *JUnit based xml reports* as table.
  JUnit exports are supported by:

  * `pytest <https://docs.pytest.org/en/latest/usage.html#creating-junitxml-format-files>`_
  * `nosetest <http://nose.readthedocs.io/en/latest/plugins/xunit.html#module-nose.plugins.xunit>`_
  * Other test frameworks (including frameworks from java and co.) support also the JUnit format.

* Shows **test environment information** from `tox-envreport <http://tox-envreport.readthedocs.io/en/latest/>`_
  based exports as table. (E.g. used operating system, python version, installed packages, ...)




Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: Contents:
