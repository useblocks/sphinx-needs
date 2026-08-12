TEST DOCUMENT UBCODE COMPAT
===========================

.. req:: Requirement A
   :id: REQ_A
   :links: SPEC_A

.. spec:: Specification A
   :id: SPEC_A

.. needlist::
   :types: req
   :cypher: MATCH (n:Need) RETURN n
   :max_items: 10

.. needtable::
   :types: req
   :cypher: MATCH (n:Need) RETURN n
   :max_items: 10

.. needflow::
   :types: req
   :cypher: MATCH (n:Need) RETURN n
   :max_items: 10
   :width: 400
   :height: 300

.. needsequence::
   :start: REQ_A
   :max_items: 10
   :width: 400
   :height: 300
