Deep
====

.. test-file:: Deep report
   :file: nested_deep.xml
   :id: TF_DEEP
   :links: REQ_1
   :tags: deep
   :auto_suites:
   :auto_cases:

.. test-suite:: Hand inner
   :file: nested_deep.xml
   :suite: inner
   :id: TS_HAND_INNER

.. test-case:: Hand inner case
   :file: nested_deep.xml
   :suite: inner
   :case: test_i1
   :classname: pkg.Inner
   :id: TC_HAND_INNER

.. req:: A requirement
   :id: REQ_1
