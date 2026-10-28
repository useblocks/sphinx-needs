# sphinx-ub-directives

A Sphinx extension that reads directive declarations from `ubproject.toml`, so the same
project builds identically with Sphinx and with [ubCode](https://ubcode.useblocks.com/):

- **directive presets** (`[parse.directive_presets.<name>]`): a new directive name that is
  an existing directive with preset options, or project-wide defaults for an existing one;
- **declared template directives** (`[parse.directive_templates.<name>]`): a directive of
  your own whose output is a Jinja template, rendered with its argument, options and body
  and with plain data (`[parse.template_contexts.<name>]`);
- **`ub-template`**, a generic template directive, switched on with
  `[parse] ub_template_enabled = true`.

The normative specification is [`design/directives-contract.md`](design/directives-contract.md),
and its executable half is the two conformance corpora in `tests/fixtures/`, which ubCode
vendors.

```python
# conf.py
extensions = ["sphinx_ub_directives"]
```
