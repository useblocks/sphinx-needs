.. _test-case:

test-case
==========

``test-case`` loads the data from a given file path in ``file`` for a specified test case.

Usage
-----

.. code-block:: rst

   .. test-case:: My Test Case
      :file: my_test_data.xml
      :suite: my_tested_suite
      :case: my_case
      :classname: my_test_class
      :id: TESTCASE_1
      :other_option: This is some text that we have defined. Wow


The following options can be set:

* **id**: Unique id for the test file. If not given, generated from title.
* **file**: file path to test file. If relative, the location of ``conf.py`` folder is taken as base-folder.
* **suite**: Name of the suite.
* **case**: Name of the case.
* **classname**: Name of the test class, which contains the case.
* **status**: A status as string.
* **tags**: A comma-separated list of strings.
* **links**: A comma-separated list of IDs to other documented test_files / needs-objects.
* **collapse**: If set to "TRUE", meta data is collapsed. Can also be set to "FALSE".

The suite that ``suite`` names, in which the case is looked up, is the first top-level suite of that name in the file,
else the first suite of that name nested at any depth, in report order (a suite before the suites nested in it).
A name used under two different parents always finds the first one; there is no syntax to name a suite by its path.

A ``suite``, or ``case`` / ``classname``, that selects nothing is a ``test_reports.suite_not_found`` /
``test_reports.case_not_found`` warning located on the directive,
and a missing ``suite``, ``file``, or both ``case`` and ``classname``, a ``test_reports.option_missing`` one;
either way an error box takes the place of the need, no need is created, and the build goes on (see :ref:`tr_warnings`).
A ``test-case`` without an ``:id:`` whose generated ID another need already holds
-- with :ref:`tr_deterministic_case_ids`, the case an ``:auto_cases:`` expansion created already --
is a ``test_reports.need`` warning that says to give the directive an ``:id:`` of its own.

As different test-frameworks handle the values for test-name and test-classname differently, it is allowed
to specify only ``case`` or ``classname``. It depends on the loaded test-data, if this results in a unique test-case
or if it selects only the first found test case. The best case is to always try to specify both values, ``case`` and
``classname``.

``test-case`` creates a need of type ``testcase`` and adds the following options automatically:

* **result**: Result of the test case run: ``passed``, ``failed``, ``error``,
  ``skipped`` or ``disabled``.
* **time**: Needed time for running the test case

These options can also be used to :ref:`filter for certain test-files <filter>`.

You can add custom options to the ``test-case`` directive by configuring the :ref:`tr_extra_options` value in your ``conf.py``.
These must also be defined in either ``needs_extra_options`` or ``needs_extra_links``.



Example
-------

.. code-block:: rst

   .. test-case:: Flake8 test case
      :id: TESTCASE_1
      :file: ../tests/doc_test/utils/pytest_data.xml
      :suite: pytest
      :classname: sphinxcontrib.test_reports.test_reports
      :case: FLAKE8
      :links: TESTSUITE_1

      A pytest test case.

   .. test-case:: nose test case
      :file: ../tests/doc_test/utils/nose_data.xml
      :suite: nosetests
      :classname: test_empty_doc
      :id: TESTCASE_2

      A nosetest test case.


.. test-case:: Flake8 test case
   :id: TESTCASE_1
   :file: ../tests/doc_test/utils/pytest_data.xml
   :suite: pytest
   :classname: sphinxcontrib.test_reports.test_reports
   :more_info: This is some text that we have defined. Wow
   :case: FLAKE8
   :links: TESTSUITE_1

   A pytest test case.

.. test-case:: nose test case
   :file: ../tests/doc_test/utils/nose_data.xml
   :suite: nosetests
   :classname: test_empty_doc
   :id: TESTCASE_2

   A nosetest test case.
