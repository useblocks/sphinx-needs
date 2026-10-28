sphinx-ub-directives
====================

A Sphinx extension that reads directive declarations from ``ubproject.toml``,
so the same project builds the same with Sphinx and with `ubCode <https://ubcode.useblocks.com/>`__:

- **directive presets** (``[parse.directive_presets.<name>]``):
  a new directive name that is an existing directive with preset options,
  or project-wide defaults for an existing directive;
- **declared template directives** (``[parse.directive_templates.<name>]``):
  a directive of your own whose output is a Jinja template,
  rendered with its argument, options and body and with data you declare;
- **ub-template**, a generic template directive, switched on with ``[parse] ub_template_enabled = true``.

.. code-block:: python

   # conf.py
   extensions = ["sphinx_ub_directives"]

sphinx-needs is optional: load it too and a preset can be based on a need type,
and templates see the project's variant data exactly as ``.. if::`` does.

The behaviour both tools implement is a written contract with two conformance corpora,
kept in this package (``design/directives-contract.md``);
these pages are the user's view of it.

.. toctree::
   :maxdepth: 2

   presets
   templates
   configuration
   migrating
   changelog
