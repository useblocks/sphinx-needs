Strict schema with a constrained field in the local schema
==========================================================

The need below sets ``status`` to the value the schema constrains it to
(``open``), while leaving every sphinx-test-reports field unpopulated.

A schema that evaluates ``status`` (``const: open``) and forbids any other
field (``unevaluatedProperties: false``) must accept this need: the constrained
field is set correctly and the unpopulated sphinx-test-reports fields are
ignored.

.. req:: A requirement with a constrained status
   :id: REQ_STATUS_1
   :status: open
