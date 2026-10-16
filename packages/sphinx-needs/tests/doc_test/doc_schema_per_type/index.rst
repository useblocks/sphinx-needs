Per-type configuration example
==============================

.. req:: Brakes engage within 100 ms
   :id: R_001
   :asil: QM

.. req:: A status outside the values of its type
   :id: R_002
   :status: done

.. safety_req:: Inherits the status values of a req
   :id: SR_001
   :asil: B
   :status: done

.. safety_req:: A safety requirement without an ASIL
   :id: SR_002

.. spec:: A spec without links
   :id: S_001

.. spec:: A spec with one link
   :id: S_002
   :links: R_001

.. spec:: A spec that tries to verify
   :id: S_003
   :links: R_001
   :verifies: R_001

.. test:: A test of two requirements
   :id: T_001
   :verifies: R_001, SR_001

.. test:: A test of a spec
   :id: T_002
   :verifies: S_002

.. test:: A test of nothing
   :id: T_003

.. test:: A test of the safety requirement that was not created
   :id: T_004
   :verifies: SR_002
