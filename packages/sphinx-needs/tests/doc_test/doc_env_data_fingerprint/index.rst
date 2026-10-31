Environment fingerprint
=======================

.. toctree::

   views

.. req:: A requirement
   :id: REQ_1
   :tags: a
   :status: open
   :effort: 3
   :owner: me
   :refines: REQ_2

   It has parts: :np:`(P1) the first part` and :np:`(P2) the second`.

   .. needarch::

      {{flow(need().id)}}

.. spec:: A specification
   :id: SPEC_1
   :links: REQ_1
   :tests: REQ_1.P1
   :status: [[copy("status", "REQ_1")]]
   :duration: 2

   A dynamic function in the content: :ndf:`echo("x")`.

.. req:: A requirement with variants
   :id: REQ_2
   :tags: a
   :status: <<full:done, open>>

.. needextend:: REQ_1
   :+tags: extended

.. list2need::
   :types: req, spec

   * (REQ_L2N) listed
     * (SPEC_L2N) listed below it

.. needimport:: imp.json

.. add-need::

.. create-need::

.. needservice:: probe

.. needuml::
   :key: one

   {{flow("REQ_1")}}

Roles: :need:`REQ_1`, :need:`REQ_1.P1`, :need_count:`type == 'req'`,
:variant:`arch`, :need_incoming:`REQ_1`, :need_outgoing:`SPEC_1`.
