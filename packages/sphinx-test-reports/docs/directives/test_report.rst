.. _test_report:

test-report
===========
``test-report`` generate a complete report including test-cases, tables and statistics for a given test-file.

.. code-block:: rst

   .. test-report:: My Report
      :id: REPORT
      :file: ../tests/data/pytest_sphinx_data_short.xml

The following options must be set:

* **id**: An unique id. Will be used as prefix for all created objects.
* **file**: File path to the test file.

Optional options are:

* **tags**: comma separated list of tags. Will be set to all created test objects.
* **links**: comma separated list of links. Will be set to all created test objects.

Example
-------
Used code:

.. code-block:: rst

   .. test-report:: My Report
      :id: REPORT
      :file: ../tests/data/pytest_sphinx_data_short.xml
      :tags: my_report, awesome
      :links: SPEC_001

   .. spec:: Example specification
      :id: SPEC_001

      Used as simple link target. See Sphinx-Needs for details.


Result:

.. test-report:: My Report
   :id: REPORT
   :file: ../tests/data/pytest_sphinx_data_short.xml
   :tags: my_report, awesome
   :links: SPEC_001

   This file contains a subset of executed tests for Sphinx.

.. spec:: Example specification
      :id: SPEC_001

      Used as simple link target. See Sphinx-Needs for details.

