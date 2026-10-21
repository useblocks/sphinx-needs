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

``source_option`` can also reference an option with comma separated values.
In this case a comparions is performed for each value, which may lead to multiple links.

``tr_link`` declares what it reads to Sphinx-Needs
(`Declaring what a function reads <https://sphinx-needs.readthedocs.io/en/latest/dynamic_functions.html#dynamic-functions-reads>`_):
the ``source_option`` of its own need, and the ``target_option`` of every need.
So Sphinx-Needs computes its links with its built-in functions, in order,
and a ``links_from_filter``, a derived ``links`` or ``union`` link type,
or any other built-in function reading those links holds them,
where a Sphinx-Needs that orders it after the built-in functions read them empty.
A ``target_option`` naming the link type the call fills is a cycle (``needs.derive_cycle``).

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
