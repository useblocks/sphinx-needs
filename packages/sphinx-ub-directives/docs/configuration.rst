Configuration
=============

Everything is read from the project's ``ubproject.toml``:
the file ``needs_from_toml`` names when sphinx-needs is loaded with it,
otherwise the one found from the directory of ``conf.py`` upwards.
The tables are read when the configuration loads;
a change to any of them re-reads every document.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - What it is
   * - ``[parse.directive_presets.<name>]``
     - A directive preset: :doc:`presets`.
   * - ``[parse.directive_templates.<name>]``
     - A declared template directive: :ref:`templates_declared`.
   * - ``[parse.template_contexts.<name>]``
     - Data for templates: :ref:`templates_contexts`.
   * - ``[parse] ub_template_enabled``
     - ``true`` switches the ``ub-template`` directive on (default ``false``): :ref:`templates_ub_template`.

Paths in these tables (a template, a context file) are relative to the **source directory**,
like an ``include``, and may not leave it.

Only this one file is read. An ``extend`` chain is not followed
(``ub_directives.extend_unsupported`` says so once, when the file has an ``extend`` key and any of these tables);
ubCode follows it, so put these tables in the file Sphinx reads.

Every warning this extension emits has the type ``ub_directives``,
so ``suppress_warnings = ["ub_directives.<code>"]`` silences one code.
