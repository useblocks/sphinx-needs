# AGENTS.md — packages/ub-needs-exchange

The delta for this package. Everything repository-level — the workspace layout, the
commands, the lock, lint/format/type-check configuration, the release recipe, the pull
request requirements — is in the ROOT [`AGENTS.md`](../../AGENTS.md), and this file does
not repeat it.

## What it is

The record of the needs.json exchange format, and its reader: parsing the envelope,
selecting a version, and handing out the version's need records with their findings.
Its consumers are sphinx-needs' two readers (`needimport` and `needs_external_needs`) and
— through the conformance corpus, which it is to vendor — ubCode.
[`design/exchange-contract.md`](design/exchange-contract.md) is the normative
specification; read it before changing behaviour. The writer (`NeedsList`, still in
`sphinx_needs/needsfile.py`) and the readers' ingest policies (in `sphinx_needs/api/need.py`)
are not here yet. `src/ub_needs_exchange/need_id.py` is the grammar of a need id — how an
id splits into a namespace and a local id at `::` (contract §14) — and the only module that
spells the separator; nothing in the package calls it.

## Layout

```text
pyproject.toml            # `[project]` and `[build-system]` ONLY; `dependencies = []`
README.rst · LICENSE
src/ub_needs_exchange/
├── __init__.py           # the public API, re-exported; `__version__`
├── reader.py             # parse / load / select_version / records, the codes
├── need_id.py            # split_id / join_id / parse_namespace / namespace_prefix: the one place `::` is spelled
└── py.typed
tests/
├── test_reader.py        # what the corpus cannot state: messages, bytes, files, aliasing
├── test_conformance.py   # runs the corpus and pins its case count
├── test_imports.py       # the stdlib-only fence
├── test_draft_conformance.py       # runs the draft "2a1"'s own corpus, pins its count
├── test_need_id_conformance.py     # runs the need-id corpus, its laws, pins its counts
├── test_need_id.py       # what that corpus cannot state: messages, types
├── test_need_id_fence.py # no other module spells `::`
└── fixtures/
    ├── needs_json_reading_conformance.toml    # the SHARED corpus (ubCode vendors it)
    ├── needs_json_2a2_draft_conformance.toml  # the draft's own (experimental)
    └── need_id_conformance.toml               # the need-id grammar (SHARED: ubCode vendors it)
docs/changelog.rst        # the sphinx-mounts convention: an `Unreleased` section
design/exchange-contract.md
design/v2a2-draft.md      # the draft "2a1", read on opt-in (experimental)
```

There is no documentation site and no command line: the package has consumers, not users.

## Commands

```bash
uv run poe test-ub-needs-exchange           # the suite (no sphinx axis: it has no Sphinx)
uv run poe import-check-ub-needs-exchange   # import every module from the built wheel
uv run poe build-ub-needs-exchange          # sdist + wheel into dist/ub-needs-exchange
```

## Rules

- **Standard library only.** No Sphinx, no docutils, no `jsonschema`, no `requests`, no
  sibling member — not as a dependency and not as an import. `tests/test_imports.py`
  imports every module in a fresh interpreter and fails on anything outside the standard
  library; CI's `toolchain-free` job runs this suite where Sphinx is not installed.
- **Mechanisms, not policy.** Nothing here logs, knows a project's fields, applies
  `needs_id_regex` or an `id_prefix`, or decides what a finding is worth. Findings are
  returned as `Diagnostic` values and refusals raised as `ExchangeError`, each with a code
  the contract fixes.
- **The corpus is canonical here.** `tests/fixtures/needs_json_reading_conformance.toml`
  is the contract ubCode is to vendor byte-for-byte. Change it only together with the
  behaviour, `design/exchange-contract.md` and `EXPECTED_CASE_COUNT`, and say in the pull
  request that ubCode owes a re-vendor. `.gitattributes` and the taplo/yamlfmt excludes
  protect its bytes; never reformat it.
- **A diagnostic's `path` and every code are part of the contract**; a message is not.
  sphinx-needs prints both in its warnings, so a changed path is a changed warning there.
- **A release re-floors every consumer.** Each release rewrites sphinx-needs'
  `ub-needs-exchange>=` floor (`propagate_floors.py`) and shows it as pending in
  `poe release-plan`. Batch changes accordingly.
