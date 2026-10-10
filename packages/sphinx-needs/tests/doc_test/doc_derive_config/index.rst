Derive configuration
====================

.. req:: Requirement one
   :id: REQ_001
   :status: open
   :hours: 3
   :owner: alice
   :asil_own: B

.. spec:: Authored values
   :id: SPEC_AUTH
   :status: open
   :links: REQ_001
   :d_total: 99
   :mentions: REQ_001

   Mentions :need:`REQ_001`.

.. spec:: An authored inline call
   :id: SPEC_CALL
   :d_owner: [[copy("owner", "REQ_001")]]

.. spec:: Extended
   :id: SPEC_EXT
   :status: draft

.. needextend:: SPEC_EXT
   :d_total: 5

.. needimport:: imported.json
