Migrating from sphinx-jinja2 (and sphinx-jinja)
===============================================

``ub-template`` does what the ``jinja`` directive of
`sphinx-jinja2 <https://github.com/sphinx-extensions2/sphinx-jinja2>`__ and
`sphinx-jinja <https://github.com/tardyp/sphinx-jinja>`__ does,
restricted so that a template reads only the data and templates you declare (and its output is refused any directive known to read other content, presets of one included),
and so that the same project renders the same in ubCode.
It has its own name, so it coexists with sphinx-jinja2 in one project
(sphinx-jinja and sphinx-jinja2 cannot be loaded together: both are ``jinja``).

In ``conf.py``, the smallest move is to keep your configuration there:

.. code-block:: python

   # was: extensions = ["sphinx_jinja2"]; jinja2_contexts = {"team": {"lead": "Ada"}}
   extensions = ["sphinx_ub_directives"]
   ub_template_enabled = True
   ub_template_contexts = {"team": {"lead": "Ada"}}

and rename ``.. jinja::`` to ``.. ub-template::``.
Contexts must be data (what ``ubproject.toml`` could hold); a function or a Python object
stops the build with an error naming it, and a subclass of a plain value
(an ``IntEnum``, a ``Markup`` string) is read as that value.

**Moving to** ``ubproject.toml`` is what makes the same project render in ubCode,
which reads only that file:

.. code-block:: toml

   [parse]
   ub_template_enabled = true

   [parse.template_contexts.team]
   lead = "Ada"

In short: rename the directive, move contexts to ``ub_template_contexts`` or ``ubproject.toml`` (or a data file),
add ``/`` to sphinx-jinja ``:file:`` names, replace filters, tests and globals by data
or by a declared template, and write ``is defined`` where a template relied on lenient undefined values.

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - sphinx-jinja2 / sphinx-jinja
     - sphinx-ub-directives
     - Why
   * - ``jinja2_contexts`` / ``jinja_contexts``
     - ``ub_template_contexts`` in ``conf.py``, or ``[parse.template_contexts.<name>]``: an inline table, or ``file = …`` (JSON or TOML)
     - Data only: a context cannot hold Python objects or functions. The old names are not read.
   * - ``env`` in the context
     - Not available (``template_context_unavailable``)
     - The build environment is unbounded authority; a template must not read other documents.
   * - ``:file:``
     - Kept, with sphinx-jinja2's meaning (relative to the page; ``/`` is the source directory)
     - sphinx-jinja names are relative to ``jinja_base``: prefix them with ``/``.
   * - ``jinja_base``
     - Not available: always the source directory, symlinks out of it refused
     - The sandbox root is fixed.
   * - ``:ctx:``
     - Kept, under the context data rules
     -
   * - ``:header_char:`` (sphinx-jinja)
     - A declared template option: ``options = { header_char = { default = "=" } }``, used as ``{{ options.header_char }}``
     - It was only ever a context value.
   * - ``:header_update_levels:`` (sphinx-jinja)
     - Not available: template output may not hold a heading (``template_heading``)
     - Headings in template output are not supported in this version.
   * - ``:debug:``, ``:raw:``
     - Kept (``jinja2_debug`` is not)
     -
   * - ``jinja2_env_kwargs`` / ``jinja_env_kwargs``
     - Not available (not read)
     - One fixed language on both sides: strict undefined, no escaping, standard delimiters.
   * - ``jinja2_filters``, ``jinja2_tests``, ``jinja_filters``, ``jinja_tests``, ``jinja_globals``, ``jinja_policies``
     - Not available (not read); plain-data globals become a context
     - Filters, tests and globals are code; data has a home.
   * - Lenient undefined (sphinx-jinja)
     - Strict: ``{% if x.y %}`` on a missing ``y`` is an error
     - Write ``{% if x.y is defined %}``.
   * - Jinja2 (sphinx-jinja, sphinx-jinja2 0.0.1)
     - minijinja 2
     - No ``{% do %}`` and no Jinja2 extensions; ``min``/``max`` compare case-sensitively.
   * - Headings in the output (sphinx-jinja2 inserts them into the page)
     - Refused (``template_heading``); write a rubric, or put the heading in the page
     - Where a heading in output may nest is the part the two tools cannot yet agree on; it is deferred.
   * - Printing a container (``{{ rows }}``, ``{{ d }}``)
     - The engine's own form: ``{"a": 1}``, ``[1, "a"]``
     - sphinx-jinja2 hands minijinja Python objects, which print as Python's ``repr`` (``{'a': 1}``).
   * - The ``jinja`` directive
     - ``ub-template``, switched on with ``[parse] ub_template_enabled = true``
     - It is opt-in, as listing an extension is.
