Configuration
=============

There are two ways to configure the extension, and they say the same things:

- in the project's ``ubproject.toml``
  (the file ``needs_from_toml`` names when sphinx-needs is loaded with it,
  otherwise the one found from the directory of ``conf.py`` upwards);
- in ``conf.py``, with four configuration values.

.. important::

   ubCode reads only ``ubproject.toml``.
   To get the same result in ubCode, configure in ``ubproject.toml``;
   what you set only in ``conf.py`` is seen by a Sphinx build alone.

The settings are read when the configuration loads;
a change to any of them re-reads every document.

.. list-table::
   :header-rows: 1
   :widths: 35 30 35

   * - ``ubproject.toml``
     - ``conf.py``
     - What it is
   * - ``[parse.directive_presets.<name>]``
     - ``ub_directive_presets`` (dict)
     - Directive presets: :doc:`presets`.
   * - ``[parse.directive_templates.<name>]``
     - ``ub_directive_templates`` (dict)
     - Declared template directives: :ref:`templates_declared`.
   * - ``[parse.template_contexts.<name>]``
     - ``ub_template_contexts`` (dict)
     - Data for templates: :ref:`templates_contexts`.
   * - ``[parse] ub_template_enabled``
     - ``ub_template_enabled`` (bool)
     - ``true`` switches the ``ub-template`` directive on (default ``false``): :ref:`templates_ub_template`.

Each ``conf.py`` value has the same shape as its table, keyed by entry name:

.. code-block:: python

   ub_directive_presets = {
       "callout": {"base": "note", "append_options": {"class": "callout"}},
   }
   ub_template_contexts = {
       "team": {"lead": "Ada", "members": ["Bob", "Cy"]},
       "reqs": {"file": "data/reqs.json"},
   }

**Which wins.** A key that ``ubproject.toml`` sets under ``[parse]`` (even as an empty table)
replaces the ``conf.py`` value of that key whole: the entries are not merged.
A key the file does not set is taken from ``conf.py``,
so one project can keep its presets in the file and its contexts in ``conf.py``.
A value given on the command line with ``-D`` wins over both.

**What a value may be.** Exactly what ``ubproject.toml`` could hold:
dicts with string keys, lists (a tuple is read as a list), strings, booleans,
integers in the signed 64-bit range, floats, and dates and times.
Anything else (``None``, a set, a path, a function or any other Python object)
stops the build with a configuration error naming the setting and the key,
such as ``ub_template_contexts['site']['data']['owner']``.
Contexts are data only, as in ``ubproject.toml``.

Paths in these tables (a template, a context file) are relative to the **source directory**,
like an ``include``, and may not leave it.

Only this one file is read. An ``extend`` chain is not followed
(``ub_directives.extend_unsupported`` says so once, when the file has an ``extend`` key and any of these tables);
ubCode follows it, so put these tables in the file Sphinx reads.

Every warning this extension emits has the type ``ub_directives``,
so ``suppress_warnings = ["ub_directives.<code>"]`` silences one code.
