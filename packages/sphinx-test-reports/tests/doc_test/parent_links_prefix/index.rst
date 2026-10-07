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

Authored links that already hold the file id, with separators and spaces: the value is
handed on as written, and the file id is not appended a second time.

.. test-file:: Comma and spaces
   :id: TF_SPC
   :file: ../utils/gtest_data.xml
   :links: REQ_1 , TF_SPC
   :auto_suites:
   :auto_cases:

.. test-file:: Pipe
   :id: TF_PIPE
   :file: ../utils/gtest_data.xml
   :links: REQ_1|TF_PIPE
   :auto_suites:
   :auto_cases:
