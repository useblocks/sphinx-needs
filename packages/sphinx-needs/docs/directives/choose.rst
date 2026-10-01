.. _choose:

choose
======

.. versionadded:: 8.6.0

The ``choose`` directive includes one of several branches of content,
chosen by :ref:`variant data <filter_variant_data>` at parse time.
Its content is a list of ``when`` directives:
the first ``when`` whose condition is true is included,
and a ``when`` with no condition is the default,
included when no condition before it is true.
The content of every other ``when`` is never parsed,
so the needs inside it are never created.

.. code-block:: rst

   .. choose::

      .. when:: var.arch == "arm"

         ARM content.

         .. req:: ARM-specific requirement
            :id: REQ_ARM_001

      .. when:: var.arch == "x86"

         x86 content.

      .. a comment may stand between two branches

      .. when::

         Content for every other architecture.

A ``choose`` is the many-branched form of :ref:`if <if>`:
the example includes the ARM content, the x86 content or the default content,
and never more than one of them.

MyST Markdown
-------------

In MyST Markdown, ``choose`` and ``when`` are fenced directives like any other.
With colon fences (the ``colon_fence`` extension):

.. code-block:: md

   ::::{choose}
   :::{when} var.arch == "arm"
   ARM content.
   :::
   % a comment may stand between two branches
   :::{when}
   Content for every other architecture.
   :::
   ::::

and with backtick fences:

.. code-block:: md

   ````{choose}
   ```{when} var.arch == "arm"
   ARM content.
   ```
   ```{when}
   Content for every other architecture.
   ```
   ````

An outer fence must be longer than the fences inside it,
so a ``choose`` takes one more colon (or backtick) than its branches,
and a ``choose`` nested in a branch takes one fewer than that branch:

.. code-block:: md

   ::::::{choose}
   :::::{when} var.debug
   ::::{choose}
   :::{when} var.arch == "arm"
   ARM debug content.
   :::
   ::::
   :::::
   ::::::

``%`` starts a MyST comment, and a ``+++`` block break counts as one too.

Rules
-----

- **The first true branch wins.**
  The conditions are evaluated in order, and the first ``when`` whose condition is true is included.
  The conditions after it are not evaluated at all, so they cannot warn.
  When no condition is true and there is no default, the ``choose`` includes nothing,
  without a warning, as a false ``if`` does.
- **The default comes last.**
  A ``when`` with no condition is the default.
  A ``choose`` has at most one, and it must be its last ``when``.
- **Only branches and comments.**
  A ``choose`` may contain only ``when`` directives and comments:
  reStructuredText comments (``..``), and in MyST ``%`` comments and ``+++`` block breaks.
  In MyST, an HTML comment (``<!-- -->``) is raw HTML rather than a comment, so it is a mistake here.
  Any other content outside a branch is a mistake,
  and the needs it would create are removed again.
  A ``when`` belongs directly in a ``choose``:
  one anywhere else is a mistake too,
  whether it is written loose in the content of another ``when``
  or inside another directive in the ``choose``,
  even one that passes its content through, such as a true ``if`` or a ``rst-class``.
- **The branches are written in place.**
  Every ``when`` of a ``choose`` is written in the body of that ``choose``, in the same file,
  so that one choice is one directive in one place.
  An ``.. include::`` (in MyST, an ``{include}``) may not supply the branches;
  it may be used inside the content of a branch,
  and a whole ``choose`` may stand in an included file.
- **The included branch is ordinary content.**
  It may hold headings, which become sections where the ``choose`` stands,
  needs, any other directive, and further ``choose`` directives.
  An ``.. include::`` may supply part of the content of a branch,
  and a ``choose`` may stand in the content of a need.
- **Parse-time evaluation**, as for ``if``:
  the content of a ``when`` that is not included is never parsed,
  so its needs are never created and its mistakes are never reported.

Conditions
----------

A ``when`` condition is exactly a condition of the :ref:`if <if>` directive,
evaluated by the same code:
a Python expression over the ``var`` namespace, with no built-in functions
(see the ``if`` directive's :ref:`if_expression_context`).
A result that is not a ``bool`` is warned about and then used as its truth value, as for ``if``.

A condition wrapped onto a second line is joined with a line break,
which is a syntax error unless the break falls inside brackets or is escaped with a backslash;
keep conditions on one line.

Warnings
--------

Every mistake warns once, under the ``needs.choose`` type
(suppressible via ``suppress_warnings = ["needs.choose"]``),
at the line of the directive or the content that has it,
and skips the **whole** ``choose``: nothing of it is included, not even its default.
The mistakes are:

- ``needs_variant_data`` is not configured, even when the ``choose`` holds only a default.
- A condition cannot be evaluated (a syntax error, an unknown key, etc.) before a branch is taken.
  So a mistake that makes a condition unevaluable, such as a misspelt key or a syntax error,
  never renders a later branch or the default in its place.
  (A mistake that leaves a valid condition, such as a misspelt value, cannot be told apart
  from a condition that is false.)
- The ``choose`` contains something that is neither a ``when`` nor a comment.
  A line of only punctuation, such as ``---`` between two branches, is such content too.
- A ``when`` is written inside another directive in the ``choose`` rather than directly in it.
- A ``when`` is supplied through an include rather than written in the body of the ``choose``
  (the warning points at the ``when`` in the included file).
- The ``choose`` has more than one default ``when``, or a default that is not its last ``when``.
- The ``choose`` has no ``when`` at all.
- The ``choose`` is given an argument: the conditions go on the branches.

A ``when`` outside a ``choose`` warns as well, and its content is skipped.
A condition whose result is not a ``bool`` warns, and its truth value is used.
A mistake that docutils or MyST already reports in the content of a ``choose``,
such as an unknown directive name, is not reported a second time;
the ``choose`` is skipped all the same.

.. note::

   A directive that produces no node, written directly in a ``choose``, is not detected:
   it still runs, and the ``choose`` goes on.
   ``default-role`` is one such directive, and so is a **false** ``if``:
   it returns nothing, so the branches written inside it vanish without a warning,
   unless the ``choose`` is left with no ``when`` at all.
   Nor is a MyST substitution: a ``{{ sub }}`` in a ``choose`` whose definition holds ``when`` directives
   is expanded in place, and its branches are taken without a warning.
   Needs are the one effect of content outside a branch that is undone;
   any other (a label, a ``needextend``) stays, so keep every directive inside a ``when``.
