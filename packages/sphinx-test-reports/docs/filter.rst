.. _filter:

Filtering Test Data
===================

You can filter the documented test-data by using the directives
`needlist <https://sphinxcontrib-needs.readthedocs.io/en/latest/directives/needlist.html>`_,
`needtable <https://sphinxcontrib-needs.readthedocs.io/en/latest/directives/needtable.html>`_ and
`needflow <https://sphinxcontrib-needs.readthedocs.io/en/latest/directives/needflow.html>`_.

These filter functions and others are provided by the Sphinx extension
`Sphinx-Needs <https://sphinxcontrib-needs.readthedocs.io/en/latest/index.html>`_.
Take a look to figure out what else is possible to customize your way of working with test cases.

.. contents:: Contents
   :local:

Filterable data
---------------
``Sphinx-Test-Reports`` adds to following data to a sphinx-need-configuration:

* **Types**

   * test-file
   * test_suite
   * test_case

* **Options**

   * **file**: Test file path.
   * **suite**: Test suite name.
   * **case**: Test case name.
   * **suites**: Amount of test suites found inside a test file.
   * **cases**: Amount of test cases found inside a test file.
   * **passed**: Amount of passed test cases.
   * **skipped**: Amount of skipped test cases.
   * **errors**: Amount of test cases with errors during execution.
   * **failed**: Amount of failed test cases.

Not all options are set for all created needs.
E.g. ``test_file`` doesn't include ``case``, as it is not related to a single test case.

The filtering possibilities are really powerful, so take a look into
`Filtering needs <https://sphinxcontrib-needs.readthedocs.io/en/latest/filter.html>`_ to figure out how to get
most out of your test data.

.. _needtable_filter:

needtable - A table for all tests
---------------------------------

``needtable`` provides a feature-rich table of the needed test data.

Use it like::


   .. needtable::
      :types: Test-File
      :columns: id, file, suites, cases, passed

We set ``types`` to ``test_file`` to document needs-objects from this type only.
``Sphinx-Test-Reports`` provides also ``test_suite`` and ``test_case``.

With ``columns`` we can specify which data of a ``test_file`` we want to see.


**Example**

.. needtable::
   :types: Test-File
   :columns: id, file, suites, cases, passed

.. _needlist_filter:

needlist - A simple list
------------------------

``needlist`` provides a simple list of the filtered test-needs.

The filter possibilities are the same as for  :ref:`needtable <needtable_filter>` and :ref:`needflow <needflow_filter>`.

Usage::

   .. needlist::
      :types: Test-File
      :filter: cases.isdigit() and int(cases) > 4

``filter`` supports complex-filter operations by using a Python-statement.
In this case, we check that the ``cases`` value contains a number and this number must ne bigger as 4.

Take a look into the
`Filter string section <https://sphinxcontrib-needs.readthedocs.io/en/latest/filter.html#filter-string>`_
of the Sphinx-Needs documentations for more details and ideas how to use it.


**Example**

.. needlist::
   :types: Test-File
   :filter: cases.isdigit() and int(cases) >= 5



.. _needflow_filter:

needflow - Flow charts of linked test data
------------------------------------------

``needflow`` draws a picture of the filtered need-objects and their connections/links.

.. note::

   This features needs the installed and configured sphinx-extension
   `sphinxcontrib-plantuml <https://pypi.org/project/sphinxcontrib-plantuml/>`_.

Usage::

   .. needflow::
      :types: Test-File, Test-Suite, Test-Case
      :filter: len(links) > 0 or len(links_back) > 0

The used ``:filter:`` allows needs only, if they have an outgoing or incoming link.

**Example**

.. .. needflow::
   :types: Test-File, Test-Suite, Test-Case
   :filter: (len(links) > 0 or len(links_back) > 0) and "example" not in tags and "auto" not in tags and "pytest_sphinx" not in tags
