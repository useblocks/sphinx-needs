# sphinx-ub-directives

A Sphinx extension for defining your own directives, without writing Python:

- **directive presets**: a new directive name that is an existing directive with preset
  options, or project-wide defaults for an existing one;
- **template directives**: a directive of your own whose output is a Jinja template,
  rendered with its argument, options and body and with plain data you declare;
- **`ub-template`**, a generic template directive, switched on when you want it.

```python
# conf.py
extensions = ["sphinx_ub_directives"]

ub_directive_presets = {
    "callout": {"base": "note", "append_options": {"class": "callout"}},
}
```

Everything can be configured in `conf.py` or in `ubproject.toml`.

**With sphinx-needs** (optional): a preset can be based on a need type, and every template
sees the project's variant data as `var`, the same values `.. if::` evaluates against.

**With [ubCode](https://ubcode.useblocks.com/)**: ubCode reads the same tables from
`ubproject.toml` and implements the same behaviour, so a project configured there renders the
same text and the same needs in both. The behaviour is specified by
[`design/directives-contract.md`](design/directives-contract.md), and its executable half is
the two conformance corpora in `tests/fixtures/`, which ubCode vendors. ubCode does not read
`conf.py`: settings written there apply to the Sphinx build only.
