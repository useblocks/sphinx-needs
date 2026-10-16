Modeling need types example
============================

.. req:: Brakes engage within 100 ms
   :id: R_001
   :tags: functional

.. req:: A requirement that sets a field of tests
   :id: R_002
   :verdict: passed

.. req:: A status that requirements do not have
   :id: R_003
   :status: done

.. req:: A tag that requirements do not have
   :id: R_004
   :tags: security

.. safety_req:: Loss of braking is detected
   :id: SR_001
   :hazard: loss of braking
   :tags: safety

.. safety_req:: A safety requirement without a hazard
   :id: SR_002

.. test:: Brake timing test
   :id: T_001
   :verifies: R_001, SR_001
   :verdict: passed

.. test:: A test that verifies nothing
   :id: T_002

Safety requirements by hazard
-----------------------------

.. good-filter-start

.. needtable::
   :filter: type == "safety_req" and hazard.startswith("loss")
   :columns: id, title, hazard

.. needtable::
   :filter: hazard is not None and hazard.startswith("loss")
   :columns: id, title, hazard

.. good-filter-end

.. needtable::
   :filter: hazard.startswith("loss")
   :columns: id, title, hazard
