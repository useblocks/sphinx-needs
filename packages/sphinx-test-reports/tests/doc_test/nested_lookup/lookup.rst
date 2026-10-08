Lookup
======

``inner`` is the name of a nested suite AND of the second top-level suite: the top-level one wins.

.. test-suite:: Inner by name
   :file: nested_mixed.xml
   :suite: inner
   :id: TS_INNER

.. test-case:: Top-level case by its suite's name
   :file: nested_mixed.xml
   :suite: inner
   :case: test_top_level
   :id: TC_INNER
