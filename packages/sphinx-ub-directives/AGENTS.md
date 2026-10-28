# AGENTS.md — packages/sphinx-ub-directives

The delta for this package. Everything repository-level — the workspace layout, the
commands, the lock, lint/format/type-check configuration, the release recipe, the pull
request requirements — is in the ROOT [`AGENTS.md`](../../AGENTS.md), and this file does
not repeat it.

## What it is

The Sphinx half of three directive mechanisms that ubCode reads from `ubproject.toml`:
directive presets (`[parse.directive_presets.<name>]`), declared template directives
(`[parse.directive_templates.<name>]`, with data from `[parse.template_contexts.<name>]`)
and the generic `ub-template` directive (`[parse] ub_template_enabled`).
[`design/directives-contract.md`](design/directives-contract.md) is the normative
specification; read it before changing behaviour.

## Commands

```bash
uv run poe test-ub-directives            # the suite, both corpora included
uv run poe test-ub-directives-sphinx7    # one matrix cell (also -sphinx8, -sphinx9)
uv run poe docs-ub-directives            # the docs build (-nW)
uv run poe import-check-ub-directives    # import every module from the built wheel
```

## Rules

- **The corpora are canonical here.** `tests/fixtures/directive_presets_conformance.toml`
  and `tests/fixtures/template_directives_conformance.toml` are the contract ubCode
  vendors byte-for-byte. Change one only together with the behaviour, the contract and its
  runner's `EXPECTED_CASE_COUNT`, and say in the pull request that ubCode owes a
  re-vendor. `.gitattributes` and the taplo/yamlfmt excludes protect their bytes; never
  reformat them.
- **sphinx-needs is optional.** Nothing imports it at module level: need-type bases and
  `var` are read from its configuration only when `sphinx_needs` is in `app.extensions`.
