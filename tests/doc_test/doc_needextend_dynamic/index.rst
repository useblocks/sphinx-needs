needextend dynamic functions
============================

.. req:: Requirement 1
   :id: REQ_1

.. req:: Requirement A 1
   :id: REQ_A_1

.. req:: Requirement B 1
   :id: REQ_B_1

.. req:: Requirement C 1
   :id: REQ_C_1

.. req:: Requirement D 1
   :id: REQ_D_1

.. req:: Requirement E 1
   :id: REQ_E_1
   :tags: [[copy("id")]]
   :status: [[copy("id")]]

.. req:: Requirement E 2
   :id: REQ_E_2
   :tags: other
   :status: open

.. req:: Requirement E 3
   :id: REQ_E_3
   :tags: other
   :status: open

.. needextend:: REQ_1
   :links: [[get_matching_need_ids("REQ_A_")]];REQ_D_1

.. needextend:: REQ_1
   :+links: REQ_D_1 , [[get_matching_need_ids("REQ_B_")]]

.. needextend:: REQ_E_1
   :tags: other
   :status: other

.. needextend:: REQ_E_1
   :+tags: appended
   :+status: appended

.. needextend:: REQ_E_2
   :tags: [[copy("id")]]
   :status: [[copy("id")]]

.. needextend:: REQ_E_2
   :+tags: appended
   :+status: appended

.. needextend:: REQ_E_3
   :+tags: [[copy("id")]]
   :+status: [[copy("id")]]