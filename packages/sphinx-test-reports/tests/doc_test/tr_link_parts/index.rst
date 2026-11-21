tr_link with need parts
=======================

.. req:: With parts, written p2 first
   :id: REQ_1
   :case: K

   Parts :np:`(p2) two` and :np:`(p1) one`.

.. req:: Without parts
   :id: REQ_2
   :case: K

Each value of ``case`` is compared whole with a candidate's ``id_complete``, ``id`` or
``case``, once per value that matches: ``REQ_1.p1`` is written twice, and
``REQ_1.nope`` names a part ``REQ_1`` does not have.

.. spec:: Reader by address
   :id: SPEC_1
   :case: REQ_1.p1, REQ_2, REQ_1.p1, REQ_1.nope
   :off: [[tr_link("case", "id_complete")]]
   :by_address: [[tr_link("case", "id_complete", include_parts=True)]]

.. spec:: Reader by part id
   :id: SPEC_2
   :case: p1
   :off: [[tr_link("case", "id")]]
   :by_part_id: [[tr_link("case", "id", include_parts=True)]]

A part answers its need's ``case``; the reader is a candidate, as ``tr_link`` has
always compared it, and so is its own part.

.. spec:: Reader by case
   :id: SPEC_3
   :case: K
   :by_case: [[tr_link("case", "case")]]
   :by_case_parts: [[tr_link("case", "case", include_parts=True)]]

   Its own part, :np:`(q) mine`.
