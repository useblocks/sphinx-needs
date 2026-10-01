.. _match:

match
=====

.. versionadded:: 8.6.0

The ``match`` directive includes one of several branches of content,
chosen by :ref:`variant data <filter_variant_data>` at parse time.
Its content is a list of ``case`` directives:
the first ``case`` whose condition is true is included,
and a ``case`` with no condition is the default,
included when no condition before it is true.
The content of every other ``case`` is never parsed,
so the needs inside it are never created.

.. code-block:: rst

   .. match::

      .. case:: var.arch == "arm"

         ARM content.

         .. req:: ARM-specific requirement
            :id: REQ_ARM_001

      .. case:: var.arch == "x86"

         x86 content.

      .. a comment may stand between two cases

      .. case::

         Content for every other architecture.

A ``match`` is the many-branched form of :ref:`if <if>`:
the example includes the ARM content, the x86 content or the default content,
and never more than one of them.

MyST Markdown
-------------

In MyST Markdown, ``match`` and ``case`` are fenced directives like any other.
With colon fences (the ``colon_fence`` extension):

.. code-block:: md

   ::::{match}
   :::{case} var.arch == "arm"
   ARM content.
   :::
   % a comment may stand between two cases
   :::{case}
   Content for every other architecture.
   :::
   ::::

and with backtick fences:

.. code-block:: md

   ````{match}
   ```{case} var.arch == "arm"
   ARM content.
   ```
   ```{case}
   Content for every other architecture.
   ```
   ````

An outer fence must be longer than the fences inside it,
so a ``match`` takes one more colon (or backtick) than its cases,
and a ``match`` nested in a case takes one fewer than that case:

.. code-block:: md

   ::::::{match}
   :::::{case} var.debug
   ::::{match}
   :::{case} var.arch == "arm"
   ARM debug content.
   :::
   ::::
   :::::
   ::::::

``%`` starts a MyST comment, and a ``+++`` block break counts as one too.

Rules
-----

- **The first true case wins.**
  The conditions are evaluated in order, and the first ``case`` whose condition is true is included.
  The conditions after it are not evaluated at all, so they cannot warn.
  When no condition is true and there is no default, the ``match`` includes nothing,
  without a warning, as a false ``if`` does.
- **The default comes last.**
  A ``case`` with no condition is the default.
  A ``match`` has at most one, and it must be its last ``case``.
- **Only cases and comments.**
  A ``match`` may contain only ``case`` directives and comments:
  reStructuredText comments (``..``), and in MyST ``%`` comments and ``+++`` block breaks.
  In MyST, an HTML comment (``<!-- -->``) is raw HTML rather than a comment, so it is a mistake here.
  Any other content outside a case is a mistake,
  and the needs it would create are removed again.
  A ``case`` belongs directly in a ``match``:
  one anywhere else, including one written loose in the content of another ``case``, is a mistake too.
- **The cases are written in place.**
  Every ``case`` of a ``match`` is written in the body of that ``match``, in the same file,
  so that one choice is one directive in one place.
  An ``.. include::`` (in MyST, an ``{include}``) may not supply the cases;
  it may be used inside the content of a case,
  and a whole ``match`` may stand in an included file.
- **The included case is ordinary content.**
  It may hold headings, which become sections where the ``match`` stands,
  needs, any other directive, and further ``match`` directives.
  An ``.. include::`` may supply part of the content of a case,
  and a ``match`` may stand in the content of a need.
- **Parse-time evaluation**, as for ``if``:
  the content of a ``case`` that is not included is never parsed,
  so its needs are never created and its mistakes are never reported.

Conditions
----------

A ``case`` condition is exactly a condition of the :ref:`if <if>` directive,
evaluated by the same code:
a Python expression over the ``var`` namespace, with no built-in functions
(see the ``if`` directive's :ref:`if_expression_context`).
A result that is not a ``bool`` is warned about and then used as its truth value, as for ``if``.

A condition must fit on one line:
docutils joins a wrapped directive argument with a line break,
which makes the expression a syntax error.

Warnings
--------

Every mistake warns once, under the ``needs.match`` type
(suppressible via ``suppress_warnings = ["needs.match"]``),
at the line of the directive or the content that has it,
and skips the **whole** ``match``: nothing of it is included, not even its default.
The mistakes are:

- ``needs_variant_data`` is not configured, even when the ``match`` holds only a default.
- A condition cannot be evaluated (a syntax error, an unknown key, etc.) before a case is taken.
  So a typo in the condition of the case that should be included
  never includes a later case, or the default, in its place.
- The ``match`` contains something that is neither a ``case`` nor a comment.
- A ``case`` is supplied through an include rather than written in the body of the ``match``
  (the warning points at the ``case`` in the included file).
- The ``match`` has more than one default ``case``, or a default that is not its last ``case``.
- The ``match`` has no ``case`` at all.
- The ``match`` is given an argument: the conditions go on the cases.

A ``case`` outside a ``match`` warns as well, and its content is skipped.
A condition whose result is not a ``bool`` warns, and its truth value is used.
A mistake that docutils or MyST already reports in the content of a ``match``,
such as an unknown directive name, is not reported a second time;
the ``match`` is skipped all the same.

.. note::

   A directive that produces no node, such as ``default-role``,
   written directly in a ``match`` is not detected: it still runs, and the ``match`` goes on.
   Needs are the one effect of content outside a case that is undone;
   any other (a label, a ``needextend``) stays, so keep every directive inside a ``case``.
