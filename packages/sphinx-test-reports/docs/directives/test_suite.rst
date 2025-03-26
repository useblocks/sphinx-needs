.. _test-suite:

test-suite
==========

``test-suite`` loads the data from a given file path in ``file`` for a specified suite.

Usage
-----

.. code-block:: rst

   .. test-suite:: My Test Suite
      :file: my_test_data.xml
      :suite: my_tested_suite
      :id: TESTSUITE_1


The following options can be set:

* **id**: Unique id for the test file. If not given, generated from title.
* **file**: file path to test file. If relative, the location of ``conf.py`` folder is taken as base-folder.
* **suite**: Name of the suite.
* **status**: A status as string.
* **tags**: A comma-separated list of strings.
* **links**: A comma-separated list of IDs to other documented test_files / needs-objects.
* **collapse**: If set to "TRUE", meta data is collapsed. Can also be set to "FALSE".

``test-suite`` creates a need of type ``test-suite`` and adds the following options automatically:

* **cases**: Amount of found cases in test file.
* **passed**: Amount of passed test cases.
* **skipped**: Amount of skipped test cases.
* **failed**: Amount of failed test cases.
* **errors**: Amount of test cases which have errors during tet execution.
* **time**: Needed time for running all test cases in suite.

These options can also be used to :ref:`filter for certain test-files <filter>`.


You can add custom options to the ``test-case`` directive by configuring the :ref:`tr_extra_options` value in your ``conf.py``.
These must also be defined in either ``needs_extra_options`` or ``needs_extra_links``. 

Example
-------

.. code-block:: rst

   .. test-suite:: Flake8 results during pytest-run
      :file: ../tests/doc_test/utils/pytest_data.xml
      :suite: pytest
      :id: TESTSUITE_1

      A test suite, containing the results of the suite ooly.


.. test-suite:: Flake8 results during pytest-run
   :file: ../tests/doc_test/utils/pytest_data.xml
   :suite: pytest
   :id: TESTSUITE_1
   :links: TESTFILE_2

   A test suite, containing the results of the suite only.




