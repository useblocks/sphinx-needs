.. _test-file:

test-file
=========

``test_file`` loads the data from a given file path in ``file``.

Usage
.....

.. code-block:: rst

   .. test-file:: My Test Data
      :file: my_test_data.xml
      :id: TESTFILE_1


The following options can be set:

* **id**: Unique id for the test file. If not given, generated from title.
* **file**: file path to test file. If relative, the location of ``conf.py`` folder is taken as base-folder.
* **status**: A status as string.
* **tags**: A comma-separated list of strings.
* **links**: A comma-separated list of IDs to other documented test_files / needs-objects.
* **collapse**: If set to "TRUE", meta data is collapsed. Can also be set to "FALSE".

``test_file`` creates a need of type ``Test-File`` and adds the following options automatically:

* **suites**: Amount of found suites in test file.
* **cases**: Amount of found cases in test file.
* **passed**: Amount of passed test cases.
* **skipped**: Amount of skipped test cases.
* **failed**: Amount of failed test cases.
* **errors**: Amount of test cases which have errors during tet execution.

These options can also be used to :ref:`filter for certain Test-Files <filter>`.

Example
-------

.. code-block:: rst

   .. test-file:: common xml test data
      :file: ../tests/data/xml_data.xml
      :id: TESTFILE_1

      This test_file has very common data.
      Some options are net set, therefore their value is ``-1``

   .. test-file:: pytest test data
      :file: ../tests/data/pytest_data.xml
      :id: TESTFILE_2
      :links: TESTFILE_1

      This test_file was created by `pytest <https://docs.pytest.org/en/latest/>`_.

   .. test-file:: nose test data
      :file: ../tests/data/nose_data.xml
      :id: TESTFILE_3
      :links: TESTFILE_1
      :status: open
      :tags: pytest, data, awesome
      :collapse: FALSE

      This test_file was created by `nosetest <https://nose.readthedocs.io/en/latest/>`_.

      ``collapse`` was set to False, therefor we see its data directly.
      Also ``status`` and ``tags`` are set.


.. test-file:: common xml test data
   :file: ../tests/data/xml_data.xml
   :id: TESTFILE_1

   This test_file has very common data.
   Some options are net set, therefore their value is ``-1``

.. test-file:: pytest test data
   :file: ../tests/data/pytest_data.xml
   :id: TESTFILE_2
   :links: TESTFILE_1

   This test_file was created by `pytest <https://docs.pytest.org/en/latest/>`_.

.. test-file:: nose test data
   :file: ../tests/data/nose_data.xml
   :id: TESTFILE_3
   :links: TESTFILE_1
   :status: open
   :tags: pytest, data, awesome
   :collapse: FALSE

   This test_file was created by `nosetest <https://nose.readthedocs.io/en/latest/>`_.

   ``collapse`` was set to False, therefor we see its data directly.
   Also ``status`` and ``tags`` are set.

