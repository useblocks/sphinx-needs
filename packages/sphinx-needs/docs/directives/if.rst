.. _ubcode: https://ubcode.useblocks.com/

.. _if:

if, elif, else
==============

.. versionadded:: 8.2.0

   ``if``

.. versionadded:: 8.6.0

   ``elif`` and ``else``

The ``if`` directive conditionally includes or excludes content based on
:ref:`variant data <filter_variant_data>` evaluated at parse time.
It may be followed by :ref:`elif and else <elif>` branches.

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

.. _elif:
.. _else:

Chains with elif and else
~~~~~~~~~~~~~~~~~~~~~~~~~

An ``if`` may be followed by any number of ``elif`` branches and one ``else``, as in
Python. At most one branch of a chain is included: the first one whose condition is
true, or the ``else`` if none is.

.. code-block:: rst

   .. if:: var.arch == "arm"

      ARM content.

   .. elif:: var.arch == "x86"

      x86 content.

   .. else::

      Content for every other architecture.

- The branches of a chain are siblings: an ``elif`` or ``else`` must be at the same
  indentation as its ``if``, and only comments may stand between two branches. Any
  other content ends the chain, and a following ``elif`` or ``else`` is reported as
  having no preceding ``if``.
- Once a branch is taken, the conditions of the later ``elif`` branches are not
  evaluated at all, so they cannot warn.
- ``else`` takes no condition. Write ``elif`` for one.
- A chain may cross an ``.. include::`` boundary: an ``if`` in the including file and an
  ``else`` at the start of the included file form one chain, and so does the reverse,
  because the included lines are parsed in place.
- A condition must fit on one line, for ``if`` and ``elif`` alike: docutils joins a
  wrapped argument with a line break, which makes the expression a syntax error.
- Chains work in reStructuredText and in MyST Markdown.

.. note::

   `ubCode`_ supports ``if`` but not yet ``elif`` and ``else``, so for now a chain is
   specific to Sphinx-Needs.

   The `sphinx-ifelse <https://github.com/x-as-code/sphinx-ifelse>`__ extension registers
   directives with the same three names, so the two extensions cannot be used together.

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

The directives emit warnings (suppressible via ``suppress_warnings = ["needs.if"]``) when:

- ``needs_variant_data`` is not configured but the directive is used.
- The expression raises an exception (syntax error, unknown key, etc.).
- The expression does not return a bool (the result is still used, as its truth value).
- An ``elif`` or ``else`` has no preceding ``if`` or ``elif``, or follows an ``else``.
- An ``else`` is given a condition.

Every problem fails closed: the branch that caused it is skipped, and so is every later
branch of the same chain, without further warnings. A typo in an ``if`` condition
therefore never renders the ``else`` fallback in its place.
