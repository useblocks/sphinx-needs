EXTRA LINKS DOCUMENT
====================

Stories
-------

.. story:: My requirement
   :id: REQ_001
   :blocks: REQ_003, DEAD_LINK_ALLOWED

.. story:: My requirement 2
   :id: REQ_002

.. story:: My requirement 3
   :id: REQ_003

.. story:: My requirement 4
   :id: REQ_004
   :links: ANOTHER_DEAD_LINK

.. story:: Req 5
   :id: REQ_005
   :blocks: REQ_001

   :need_part:`(1) awesome part`

   :need_part:`(cool) a cool part`


Tests
-----

.. test:: Test of requirements
   :id: TEST_001
   :tests: REQ_001, REQ_003

.. test:: Test of requirements2
   :id: TEST_002
   :tests: REQ_001

.. test:: Test of requirements 5
   :id: TEST_003
   :tests: REQ_005.1,REQ_005.cool

.. test:: Test of invalid need_part links
   :id: TEST_004
   :tests: REQ_005.1,REQ_005.invalid
