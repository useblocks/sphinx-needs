Up
==

.. toctree::

   inc_host
   imp
   auto
   svc

Requirements
------------

.. req:: The first
   :id: REQ_1
   :status: open
   :tags: a, b
   :asil: B

   A body with :np:`(p1) the part`.

.. req:: The second
   :id: REQ_2
   :links: REQ_1.p1, REQ_3[status == "open"]

   Links to a part and, under a condition, to a need.

.. req:: The third
   :id: REQ_3
   :status: open

   .. req:: Nested
      :id: REQ_4

.. req:: Parts out of id order
   :id: REQ_5

   Parts :np:`(zeta) last id first`, :np:`(alpha) first id second` and
   :np:`(mid) middle`.

Specifications
--------------

.. spec:: A spec
   :id: SPEC_1
   :verdict: pass
   :implements: REQ_2

.. spec:: Links to the empty part
   :id: SPEC_2
   :implements: REQ_5., REQ_5.alpha
