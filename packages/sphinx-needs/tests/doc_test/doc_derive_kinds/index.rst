Derive kinds
============

.. req:: Req A
   :id: REQ_A
   :status: open
   :hours: 2
   :points: 3
   :score: 0.5
   :owner: alice
   :labels: x, y
   :asil_own: B
   :passed: true

   Part :np:`(p) part p`, and a mention of :need:`REQ_B`.

.. req:: Req B
   :id: REQ_B
   :status: closed
   :hours: 5
   :points: 4
   :score: 1e16
   :owner: bob
   :labels: y, z
   :asil_own: A
   :passed: false

.. req:: Größe
   :id: REQ_C
   :status: open
   :owner: carol
   :asil_own: D

.. spec:: Spec 1
   :id: SPEC_1
   :links: REQ_B, REQ_A, REQ_A, REQ_A.p, NOPE_1
   :parent: REQ_B, REQ_A

   Mentions :need:`REQ_B`, :need:`REQ_A.p`, :need:`NOPE_2`, :need:`SPEC_1` and :need:`REQ_B` again.

.. test:: Test 1
   :id: TEST_1
   :tests: SPEC_1
   :status: passed
   :hours: 1
   :passed: true

.. test:: Test 2
   :id: TEST_2
   :tests: SPEC_1
   :status: failed
   :passed: false

.. req:: Transitive 1
   :id: TRANS_1
   :asil_own: QM
   :satisfies: TRANS_2

.. req:: Transitive 2
   :id: TRANS_2
   :asil_own: A
   :satisfies: TRANS_3

.. req:: Transitive 3
   :id: TRANS_3
   :asil_own: C
   :satisfies: TRANS_2

.. req:: Transitive 4
   :id: TRANS_4
   :asil_own: D
   :satisfies: TRANS_1
