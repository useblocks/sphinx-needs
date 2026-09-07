Variant Data Extension Write
============================

.. req:: A requirement
   :id: REQ_EXT

Role renders: :variant:`env`

The two counts below must agree with the role: the value the role renders is the one
a ``var.*`` filter expression has to match.

Extension value: :need_count:`var.env == "from_extension"`

File value: :need_count:`var.env == "production"`
