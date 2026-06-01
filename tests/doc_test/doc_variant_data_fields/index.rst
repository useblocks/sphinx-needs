Variant Data Fields Test
========================

.. req:: Scalar string from variant data
   :id: REQ_001
   :mystring: <{ var.platform }>

.. req:: Embedded string from variant data
   :id: REQ_002
   :mystring: platform is <{ var.platform }>!

.. req:: Integer from variant data
   :id: REQ_003
   :myint: <{ var.build.opt_level }>

.. req:: Array from variant data
   :id: REQ_004
   :myarray: a, <{ var.platform }>, c

.. req:: Syntax not parsed when parse_variants is False
   :id: REQ_005
   :mynoparse: <{ var.platform }>
