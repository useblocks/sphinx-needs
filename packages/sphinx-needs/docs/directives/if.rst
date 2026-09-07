.. _if:

if
==

.. versionadded:: 8.2.0

The ``if`` directive conditionally includes or excludes content based on
:ref:`variant data <filter_variant_data>` evaluated at parse time.

The directive argument is a Python expression evaluated against the ``var``
namespace (populated from :ref:`needs_variant_data`).
If the expression evaluates to ``True``, the directive body is parsed and
included in the document. Otherwise the entire body is skipped.

.. code-block:: rst

   .. if:: var.arch == "arm"

      This paragraph only appears when ``needs_variant_data``
      has ``arch`` set to ``"arm"``.

      .. req:: ARM-specific requirement
         :id: REQ_ARM_001

         This need is only created for the ARM variant.

Usage
-----

Basic conditions
~~~~~~~~~~~~~~~~

.. code-block:: rst

   .. if:: var.debug

      Debug-only content here.

   .. if:: var.build.optimization > 1

      High-optimization content.

Membership tests
~~~~~~~~~~~~~~~~

.. code-block:: rst

   .. if:: "feature_x" in var.build.features

      Feature X documentation.

Nested if directives
~~~~~~~~~~~~~~~~~~~~

``if`` directives can be nested:

.. code-block:: rst

   .. if:: var.arch == "arm"

      .. if:: var.debug

         ARM debug-specific content.

Content with sections
~~~~~~~~~~~~~~~~~~~~~

The body may contain section headers and any valid reStructuredText:

.. code-block:: rst

   .. if:: var.arch == "arm"

      ARM-specific section
      ~~~~~~~~~~~~~~~~~~~~

      Content under a conditional heading.

Expression context
------------------

Only the ``var`` namespace is available in the expression.
Built-in Python functions (``open``, ``import``, etc.) are **not** accessible.

If the expression references a variant key that does not exist, a warning is
emitted and the content is skipped.

Supported operators:

- Comparison: ``==``, ``!=``, ``<``, ``>``, ``<=``, ``>=``
- Logical: ``and``, ``or``, ``not``
- Membership: ``in``
- Attribute access: ``var.a.b.c`` (nested dicts)

Behavior
--------

- **Parse-time evaluation**: The condition is evaluated during RST parsing.
  Unlike Sphinx's ``only`` directive (which defers to doctree resolution),
  excluded content is never parsed at all.
- **No need data access**: Because parsing happens before all needs are
  collected, need fields and IDs are not available in the expression.
  Use :ref:`filter` for need-aware filtering.
- **Incremental builds**: If a document is re-read (e.g., because the source
  changed), all ``if`` directives in it are re-evaluated.

Warnings
--------

The directive emits warnings (suppressible via ``suppress_warnings = ["needs.if"]``) when:

- ``needs_variant_data`` is not configured but the directive is used.
- The expression raises an exception (syntax error, unknown key, etc.).
