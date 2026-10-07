tr_link, as documented
======================

.. spec:: sphinxcontrib.test_reports.test_reports
   :id: TESTSPEC_001

A need TITLED ``None``: a fix that coerced the missing value to a string would link it.

.. spec:: None
   :id: TESTSPEC_NONE

A test-file carries no ``classname``: the field is registered on every need, with the value ``None``.

.. test-file:: A test file with the same role
   :id: TESTFILE_1
   :file: ../utils/pytest_data.xml
   :links: [[tr_link('classname', 'title')]]

.. test-case:: Flake8 test case
   :id: TESTLINK_1
   :file: ../utils/pytest_data.xml
   :suite: pytest
   :classname: sphinxcontrib.test_reports.test_reports
   :case: FLAKE8
   :links: [[tr_link('classname', 'title')]]

The other direction: the targets are compared on ``classname``, which only the test-case
carries -- every other need, the test-file included, is a target whose value is ``None``.

.. spec:: sphinxcontrib.test_reports.test_reports
   :id: TESTSPEC_002
   :links: [[tr_link('title', 'classname')]]
