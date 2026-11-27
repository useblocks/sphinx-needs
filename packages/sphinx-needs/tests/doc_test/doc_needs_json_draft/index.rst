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

Specifications
--------------

.. spec:: A spec
   :id: SPEC_1
   :verdict: pass
   :implements: REQ_2
