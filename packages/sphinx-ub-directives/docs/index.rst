sphinx-ub-directives
====================

A Sphinx extension for defining your own directives, without writing Python:

- **directive presets**:
  a new directive name that is an existing directive with preset options,
  or project-wide defaults for an existing directive (:doc:`presets`);
- **template directives**:
  a directive of your own whose output is a Jinja template,
  rendered with its argument, options and body and with plain data you declare (:doc:`templates`);
- **ub-template**, a generic template directive, switched on when you want it.

.. code-block:: python

   # conf.py
   extensions = ["sphinx_ub_directives"]

   ub_directive_presets = {
       "callout": {"base": "note", "append_options": {"class": "callout"}},
   }

Everything can be configured in ``conf.py``, or in ``ubproject.toml`` (:doc:`configuration`).
Coming from sphinx-jinja or sphinx-jinja2? See :doc:`migrating`.

With sphinx-needs
-----------------

sphinx-needs is optional. Load it too, and a preset can be based on a need type,
and every template sees the project's variant data as ``var``,
the same values ``.. if::`` evaluates against.

With ubCode
-----------

`ubCode <https://ubcode.useblocks.com/>`__ reads the same tables from ``ubproject.toml``
and implements the same behaviour,
so a project configured there renders the same text and the same needs in both.
That behaviour is a written contract with two conformance corpora, kept in this package
(``design/directives-contract.md``), and both implementations are tested against them.
ubCode does not read ``conf.py``: settings written there apply to the Sphinx build only.

.. toctree::
   :maxdepth: 2

   presets
   templates
   configuration
   migrating
   changelog
