Parent links
============

.. spec:: An id the file id is a prefix of
   :id: TF_PRFX

.. spec:: A requirement
   :id: REQ_1

``TF_PRF`` is a substring of ``TF_PRFX``, but not one of its links.

.. test-file:: Parent links
   :id: TF_PRF
   :file: ../utils/gtest_data.xml
   :links: TF_PRFX
   :auto_suites:
   :auto_cases:

The control: an authored link that shares no prefix with the file id.

.. test-file:: Control
   :id: TF_CTL
   :file: ../utils/gtest_data.xml
   :links: REQ_1
   :auto_suites:
   :auto_cases:
