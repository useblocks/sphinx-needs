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
`Sphinx-Needs <https://sphinx-needs.readthedocs.io/en/latest/>`_.
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
In the last years, we have created additional information and extensions, which are based on or related to Sphinx-Needs:

.. grid:: 2
    :gutter: 2

    .. grid-item-card::
        :columns: 12 6 6 6
        :link: https://sphinx-needs.com
        :img-top: /_static/sphinx-needs-card.png
        :class-card: border

        Sphinx-Needs.com
        ^^^^^^^^^^^^^^^^
        The website presents the essential Sphinx-Needs functions and related extensions.

        Also, it is a good entry point to understand the benefits and get an idea about the complete ecosystem of Sphinx-Needs.
        +++

        .. button-link:: https://sphinx-needs.com
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`globe;1em;sd-text-primary` Sphinx-Needs.com

    .. grid-item-card::
        :columns: 12 6 6 6
        :link: https://sphinx-needs.readthedocs.io/en/latest/
        :img-top: /_static/sphinx-needs-card.png
        :class-card: border

        Sphinx-Needs
        ^^^^^^^^^^^^
        Create, update, link, filter and present need objects like Requirements, Specifications, Bugs and many more.

        The base extension provides all of its functionality under the MIT license for free.
        +++

        .. button-link:: https://sphinx-needs.readthedocs.io/en/latest/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs

    .. grid-item-card::
        :columns: 12 6 6 6
        :link: https://useblocks.com/sphinx-needs-enterprise/
        :img-top: /_static/sphinx-needs-enterprise-card.png
        :class-card: border

        Sphinx-Needs Enterprise
        ^^^^^^^^^^^^^^^^^^^^^^^
        Synchronize Sphinx-Needs data with external, company internal systems like CodeBeamer, Jira or Azure Boards.

        Provides scripts to baseline data and makes CI usage easier.
        +++

        .. button-link:: http://useblocks.com/sphinx-needs-enterprise/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs

    .. grid-item-card::
        :columns: 12 6 6 6
        :link: https://sphinx-test-reports.readthedocs.io/en/latest/
        :img-top: /_static/sphinx-test-reports-logo.png
        :class-card: border

        Sphinx-Test-Reports
        ^^^^^^^^^^^^^^^^^^^
        Extension to import test results from XML files as **need** objects.

        Created **need** objects can be filtered and linked to specification objects.
        +++

        .. button-link:: https://sphinx-test-reports.readthedocs.io/en/latest/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs


Other Sphinx extensions
~~~~~~~~~~~~~~~~~~~~~~~
During the use of Sphinx-Needs in popular companies’ internal projects,
we have created other Sphinx extensions to support the work of teams in the automotive industry:

.. grid:: 2
    :gutter: 2

    .. grid-item-card::
        :columns: 12 6 6 6
        :link: https://sphinx-collections.readthedocs.io/en/latest/
        :img-top: /_static/sphinx_collections_logo.png
        :class-card: border

        Sphinx Collections
        ^^^^^^^^^^^^^^^^^^
        Extension to collect or generate files from different sources and include them in the Sphinx source folder.

        It supports sources like Git repositories, Jinja based files or symlinks.
        +++

        .. button-link:: https://sphinx-collections.readthedocs.io/en/latest/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs

    .. grid-item-card::
        :columns: 12 6 6 6
        :link: https://sphinx-bazel.readthedocs.io/en/latest/
        :img-top: /_static/sphinx_bazel_logo.png
        :class-card: border

        Sphinx Bazel
        ^^^^^^^^^^^^
        Provides a Bazel domain in Sphinx documentation and allows the automated import of Bazel files and their documentation.
        +++

        .. button-link:: https://sphinx-bazel.readthedocs.io/en/latest/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs


Motivation
----------
``Sphinx-Test-Reports`` was created for an automotive project, which needs to document test results and their used
environment configuration in an human-readable format.
The goal is to provide enough information to be able to setup an identical test environment in 20+ years.

``Sphinx-Test-Reports`` is part of a software bundle, which was designed to fulfill
the parameters of the `ISO 26262 <https://en.wikipedia.org/wiki/ISO_26262>`_ standard
for safety critical software in automotive companies.

Other tools are:
`sphinx-needs <http://sphinx-needs.readthedocs.io/en/latest/>`__,
`sphinx-collections <https://sphinx-collections.readthedocs.io/en/latest/>`__ and
`tox-envreport <http://tox-envreport.readthedocs.io/en/latest/>`__.

