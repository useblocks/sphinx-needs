.. _test-case:

test-case
==========

``test-case`` loads the data from a given file path in ``file`` for a specified test case.

Usage
-----

.. code-block:: rst

   .. test-case:: My Test Suite
      :file: my_test_data.xml
      :suite: my_tested_suite
      :case: my_case
      :classname: my_test_class
      :id: TESTCASE_1


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

As different test-frameworks handle the values for test-name and test-classname differently, it is allowed
to specify only ``case`` or ``classname``. It depends on the loaded test-data, if this results in a unique test-case
or if it selects only the first found test case. The best case is to always try to specify both values, ``case`` and
``classname``.

``test-suite`` creates a need of type ``Test-Suite`` and adds the following options automatically:

* **result**: Result of the test case run. E.g passed or failed.
* **time**: Needed time for running the test case

These options can also be used to :ref:`filter for certain Test-Files <filter>`.

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
   :case: FLAKE8
   :links: TESTSUITE_1

   A pytest test case.

.. test-case:: nose test case
   :file: ../tests/doc_test/utils/nose_data.xml
   :suite: nosetests
   :classname: test_empty_doc
   :id: TESTCASE_2

   A nosetest test case.



