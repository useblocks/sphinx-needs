# AGENTS.md — packages/ubproject

The delta for this package. Everything repository-level — the workspace layout, the
commands, the lock, lint/format/type-check configuration, the release recipe, the pull
request requirements — is in the ROOT [`AGENTS.md`](../../AGENTS.md), and this file does
not repeat it.

## What it is

The shared reader for `ubproject.toml`: finding and loading the file, selecting a table,
anchoring relative paths, the `[variants]` table with its `[needs] variant_data*`
fallback, and the one copy of the variant-data merge. Its consumers will be the four Sphinx
extensions in this repository, one pull request each after its first release, and —
through the conformance corpus, which it is to vendor — ubCode.
[`design/reading-contract.md`](design/reading-contract.md) is the normative specification;
read it before changing behaviour.

## Layout

```text
pyproject.toml            # `[project]` and `[build-system]` ONLY; `dependencies = []`
README.rst · LICENSE
src/ubproject/
├── __init__.py           # the public API, re-exported; `__version__`
├── project.py            # find / load / select / anchor, and `UbprojectError`
├── variants.py           # `read_variants`, `Diagnostic`, `VariantsResult`, the codes
├── variant_data.py       # validate / load / deep_merge / resolve
└── py.typed
tests/
├── test_*.py             # one module per source module, plus the two below
├── test_conformance.py   # runs the corpus and pins its case count
├── test_imports.py       # the stdlib-only fence
└── fixtures/ubproject_reading_conformance.toml
docs/changelog.rst        # the sphinx-mounts convention: an `Unreleased` section
design/reading-contract.md
```

There is no documentation site and no command line: the package has consumers, not users.

## Commands

```bash
uv run poe test-ubproject              # the suite (no sphinx axis: it has no Sphinx)
uv run poe import-check-ubproject      # import every module from the built wheel
uv run poe build-ubproject             # sdist + wheel into dist/ubproject
```

## Rules

- **Standard library only.** No Sphinx, no docutils, no sibling member — not as a
  dependency and not as an import. `tests/test_imports.py` imports every module in a
  fresh interpreter and fails on anything outside the standard library; CI's
  `toolchain-free` job runs this suite where Sphinx is not installed.
- **Mechanisms, not policy.** Nothing here logs, reads a Sphinx config, handles `-D` or
  `-c`, or decides discovery. Findings are returned as `Diagnostic` values and failures
  raised as `UbprojectError`; the consumer decides what either is worth.
- **The corpus is canonical here.** `tests/fixtures/ubproject_reading_conformance.toml` is
  the contract ubCode is to vendor byte-for-byte. Change it only together with the behaviour,
  `design/reading-contract.md` and `EXPECTED_CASE_COUNT`, and say in the pull request that
  ubCode owes a re-vendor. `.gitattributes` and the taplo/yamlfmt excludes protect its
  bytes; never reformat it.
- **Tests build paths with `Path`**, never `"a/b"` literals, and read and write text with
  an explicit `encoding`, so that it holds on Windows too — its consumers' suites run
  there, and ubCode's users are on every platform.
- **A release re-floors every consumer.** Once the extensions depend on this package, each
  release of it rewrites their `ubproject>=` floor (`propagate_floors.py`) and shows them
  as pending in `poe release-plan`. Batch changes accordingly.
