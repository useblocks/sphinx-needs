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

## Layout

```text
src/sphinx_ub_directives/
├── __init__.py       # setup(): the confval, the lookup wrapper, the builder-inited registrations
├── _config.py        # reading the one ubproject.toml at config-inited (contract §2)
├── _presets.py       # presets: the checks and the subclass of each base (§3)
├── _engine.py        # minijinja: the dialect, the sandboxed loader, the data model, render() (§4, §7)
├── _templates.py     # contexts, var, declared template directives, the breaker and the splice (§4, §5, §7)
├── _refusal.py       # depth 1 and only declared inputs: the directive-lookup wrapper (§7.10)
└── _ub_template.py   # the ub-template directive (§6)
tests/
├── corpus.py                        # the runner half both corpora share
├── test_presets_conformance.py      # the presets corpus, its count and shape fences
├── test_templates_conformance.py    # the template corpus, its count and shape fences
├── test_presets.py · test_templates.py · test_config.py · test_minijinja_version.py
└── fixtures/*_conformance.toml      # CANONICAL; ubCode vendors them
tools/check_minijinja_version.py     # the lock resolves the minijinja the template corpus records
design/directives-contract.md        # the normative contract
docs/                                # the package's own site (.readthedocs.yaml beside this file)
```

## Commands

```bash
uv run poe test-ub-directives            # the suite, both corpora included
uv run poe test-ub-directives-sphinx7    # one matrix cell (also -sphinx8, -sphinx9)
uv run poe docs-ub-directives            # the docs build (-nW)
uv run poe import-check-ub-directives    # import every module from the built wheel
python packages/sphinx-ub-directives/tools/check_minijinja_version.py   # the version fence
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
- **One render seam.** Every template renders through `_engine.render`, and every output that
  joins a page passes `_templates.observe`, which the template runner patches to read the
  expansions. Keep both single.
- **A template expansion in the corpus is checked on two engines.** When adding a template
  case, render its expansion with minijinja-py in the contract's dialect AND with a Rust
  minijinja of the version the header records, configured as contract §7.1 says; a case
  whose two renders differ is a contract question, not a case.
