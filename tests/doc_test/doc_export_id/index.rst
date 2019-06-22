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

.. needlist::
   :export_id: list_1


Tables
------

.. needtable::
   :status: open

.. needtable::
   :export_id: table_1

.. needtable::
   :filter: "test" in type
   :export_id: table_2

Flow
----

.. needflow::

.. needflow::
   :export_id: flow_1

.. needflow::
   :export_id: flow_2
   :filter: is_need is False or type != "story"



.. uml::

   node test
   node test_2

   node spec
   cloud spec_1 as s1 [[https.spiegel.de]] #ffcc00 {

    node spec_1.2 as s11
   }

    test --> s1
    test_2 --> s11

