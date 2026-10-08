Hand-written over nested suites
===============================

A suite that exists only nested, and one of its cases.

.. test-suite:: Nested only
   :file: pytest_nested_example.xml
   :suite: nested_example
   :id: TS_HAND

.. test-case:: Nested case
   :file: pytest_nested_example.xml
   :suite: nested_example
   :case: FLAKE8
   :classname: docs.conf
   :id: TC_HAND
