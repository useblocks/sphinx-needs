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
.. image:: https://github.com/useblocks/sphinx-test-reports/actions/workflows/ci.yaml/badge.svg
    :target: https://github.com/useblocks/sphinx-test-reports/actions/
    :alt: CI Build Status
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


Sphinx-Needs Ecosystem
----------------------
In the last years additional information and extensions have been created, which are based or related to Sphinx-Needs:


.. panels::
   :container: container-lg pb-3
   :column: col-lg-6 col-md-6 col-sm-4 col-xs-4 p-2
   :img-top-cls: pl-5 pr-5 pt-2 pb-2

   ---
   :img-top: /_static/sphinx-needs-card.png
   :img-top-cls: + bg-light

   Sphinx-Needs.com
   ^^^^^^^^^^^^^^^^
   Webpage to present most important Sphinx-Needs functions and related extensions.

   Good entrypoint to understand the benefits and to get an idea about the complete ecosystem of Sphinx-Needs.

   +++

   .. link-button:: https://sphinx-needs.com
       :type: url
       :text: Sphinx-Needs.com
       :classes: btn-secondary btn-block

   ---
   :img-top: /_static/sphinx-needs-card.png

   Sphinx-Needs
   ^^^^^^^^^^^^
   Base extension, which provides all of its functionality under the MIT license for free.

   Create, update, link, filter and present need objects like Requirements, Specifications, Bugs and much more.

   +++

   .. link-button:: https://sphinxcontrib-needs.readthedocs.io/en/latest/
       :type: url
       :text: Technical docs
       :classes: btn-secondary btn-block

   ---
   :img-top: /_static/sphinx-needs-enterprise-card.png

   Sphinx-Needs Enterprise
   ^^^^^^^^^^^^^^^^^^^^^^^
   Synchronizes Sphinx-Needs data with external, company internal systems like CodeBeamer, Jira or Azure Boards.

   Provides scripts to baseline data and make CI usage easier.
   +++

   .. link-button:: http://useblocks.com/sphinx-needs-enterprise/
       :type: url
       :text: Technical docs
       :classes: btn-secondary btn-block

   ---
   :img-top: /_static/sphinx-test-reports-card.png

   Sphinx-Test-Reports
   ^^^^^^^^^^^^^^^^^^^
   Extension to import test results from xml files as need objects.

   Created need objects can be filtered and e.g. linked to specification objects.
   +++

   .. link-button:: https://sphinx-test-reports.readthedocs.io/en/latest/
       :type: url
       :text: Technical docs
       :classes: btn-secondary btn-block


Further Sphinx extensions
^^^^^^^^^^^^^^^^^^^^^^^^^
During the work with Sphinx-Needs in bigger, company internal projects, other Sphinx extensions have been created
to support the work in teams of the automotive industry:

.. panels::
   :container: container-lg pb-3
   :column: col-lg-6 col-md-6 col-sm-4 col-xs-4 p-2
   :img-top-cls: pl-5 pr-5 pt-2 pb-2

   ---
   :img-top: /_static/sphinx_collections_logo.png


   Extension to collect or generate files from different sources and include them into the Sphinx source folder.

   Sources like git repositories, jinja based files or symlinks are supported.

   +++

   .. link-button:: https://sphinx-collections.readthedocs.io/en/latest/
       :type: url
       :text: Technical docs
       :classes: btn-secondary btn-block

   ---
   :img-top: /_static/sphinx_bazel_logo.png


   Provides a Bazel domain in Sphinx documentations and allows the automated import of Bazel files and their
   documentation.

   +++

   .. link-button:: https://sphinx-bazel.readthedocs.io/en/latest/
       :type: url
       :text: Technical docs
       :classes: btn-secondary btn-block


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

