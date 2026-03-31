LINK CONDITIONS TEST
=====================

Requirements
------------

.. req:: Requirement Open
   :id: REQ_001
   :status: open

.. req:: Requirement Closed
   :id: REQ_002
   :status: closed

.. req:: Requirement Done
   :id: REQ_003
   :status: done

Specifications
--------------

.. spec:: Spec with passing condition
   :id: SPEC_001
   :links: REQ_001[status=="open"]

   Links to REQ_001 with a condition that should pass.

.. spec:: Spec with failing condition
   :id: SPEC_002
   :links: REQ_002[status=="open"]

   Links to REQ_002 with a condition that should fail (REQ_002 has status "closed").

.. spec:: Spec with invalid condition syntax
   :id: SPEC_003
   :links: REQ_001[status===]

   Links to REQ_001 with invalid filter syntax.

.. spec:: Spec with no condition
   :id: SPEC_004
   :links: REQ_001

   Links to REQ_001 with no condition (should always pass).

.. spec:: Spec with multiple links mixed conditions
   :id: SPEC_005
   :links: REQ_001[status=="open"], REQ_003[status=="open"]

   First link condition passes, second fails (REQ_003 has status "done").

.. spec:: Spec with multi-bracket condition
   :id: SPEC_006
   :links: REQ_001[["open" in tags]]

   Uses double brackets; the condition fails because REQ_001 has no tag "open".

Imported Needs
--------------

.. needimport:: needs_test_conditions.json

Parse Conditions Disabled
-------------------------

.. spec:: Spec with raw link containing brackets
   :id: SPEC_RAW_001
   :raw_links: REQ_001[status=="open"]

   The ``raw_links`` link type has ``parse_conditions: False``,
   so the brackets are treated as literal ID text, not as a condition.
