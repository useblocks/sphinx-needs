EXTRA LINKS DOCUMENT
====================

Stories
-------

.. story:: My requirement
   :id: REQ_001
   :links: REQ_002, REQ_004
   :blocks: REQ_003

.. story:: My requirement 2
   :id: REQ_002

.. story:: My requirement 3
   :id: REQ_003

.. story:: My requirement 4
   :id: REQ_004

.. story:: Req 5
   :id: REQ_005
   :links: REQ_001
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
   :links: TEST_001
   :tests: REQ_001

.. test:: Test of requirements 5
   :id: TEST_003
   :links: REQ_005.1
   :tests: REQ_005.1,REQ_005.cool


Lists
-----

.. needlist::


Tables
------

.. needtable::

.. needtable::
   :columns: id, incoming, outgoing

.. needtable::
   :columns: id, incoming, outgoing, blocks, blocks_back, tests, tests_back


Flow
----

.. needflow::
   :show_legend:
   :filter: is_need

.. needflow::
   :show_legend:
   :filter: is_need
   :show_link_names:
