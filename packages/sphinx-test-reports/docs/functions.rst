:hide-navigation:

Dynamic functions
=================

Sphinx-Test-Reports provides dynamic functions for Sphinx-Needs.

Read chapter `Dynamic function <https://sphinx-needs.readthedocs.io/en/latest/dynamic_functions.html>`_
from Sphinx-Needs documentation to know how to use them.


tr_link
---------
Links a need (e.g testcase) automatically to other needs, which have a specific value in a given option.

**Usage**::

   .. test-case:: My test case
      :id: TESTCASE_1
      :file: my_test_file.xml
      :suite: pytest
      :classname: sphinxcontrib.test_reports.test_reports
      :case: FLAKE8
      :links: [[tr_link("source_option", "target_option")]]

``tr_link`` needs the following arguments:

* **source_option**: Name of an option of the test-need, which is used for comparision. E.g. ``classname``.
* **target_option**: Name of an option of all other needs, which is used for comparision. E.g. ``title``.

The function reads the ``target_option`` from the need, where it is used.
Then it goes through **all** other needs and checks if the value of their ``source_option`` is equal to
the ``target_option``.
If this is the case, their IDs get stored and finally returned.

**Example**::

   .. spec:: sphinxcontrib.test_reports.test_reports
      :id: TESTSPEC_001
      :status: open
      :tags: example, link_example

      This specification specifies the test case ``sphinxcontrib.test_reports.test_reports``.

   .. test-case:: Flake8 test case
      :id: TESTLINK_1
      :file: ../tests/doc_test/utils/pytest_data.xml
      :suite: pytest
      :classname: sphinxcontrib.test_reports.test_reports
      :case: FLAKE8
      :tags: example, link_example
      :links: [[tr_link('classname', 'title')]]

      A simple test case.
      We will set a link to the need, which has our classname as title.

   .. needflow::
      :tags: link_example

.. spec:: sphinxcontrib.test_reports.test_reports
   :id: TESTSPEC_001
   :status: open
   :tags: example, link_example

   This specification specifies the test case ``sphinxcontrib.test_reports.test_reports``.

.. test-case:: Flake8 test case
   :id: TESTLINK_1
   :file: ../tests/doc_test/utils/pytest_data.xml
   :suite: pytest
   :classname: sphinxcontrib.test_reports.test_reports
   :case: FLAKE8
   :tags: example, link_example
   :links: [[tr_link('classname', 'title')]]

   A simple test case.
   We will set a link to the need, which has our classname as title.

.. needflow::
   :tags: link_example
