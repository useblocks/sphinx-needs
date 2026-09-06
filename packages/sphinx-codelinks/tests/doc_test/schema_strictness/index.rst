Strict schema with unset sphinx-codelinks fields
================================================

This plain requirement does not use source tracing. It leaves the fields that
sphinx-codelinks registers globally (``project``, ``file``, ``directory`` ...)
unpopulated. A schema that forbids additional fields
(``unevaluatedProperties: false``) must therefore not report them as
unexpected.

.. req:: A plain requirement
   :id: REQ_1
