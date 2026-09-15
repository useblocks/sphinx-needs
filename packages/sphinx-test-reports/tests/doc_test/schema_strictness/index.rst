Strict schema with unpopulated sphinx-test-reports fields
=========================================================

The needs below are plain requirements. They leave every field that
sphinx-test-reports registers with sphinx-needs (``file``, ``suite``,
``case``, ``passed``, ``failed``, ``errors`` ...) unpopulated.

A schema that forbids additional fields (``unevaluatedProperties: false``)
must therefore *not* report any violation for them.

.. req:: A plain requirement
   :id: REQ_1

.. req:: Another plain requirement
   :id: REQ_2
