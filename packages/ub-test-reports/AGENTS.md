# AGENTS.md — packages/ub-test-reports

The delta for this package. Everything repository-level — the workspace layout, the
commands, the lock, lint/format/type-check configuration, the release recipe, the pull
request requirements — is in the ROOT [`AGENTS.md`](../../AGENTS.md), and this file does
not repeat it.

## What it is

The Sphinx-free core of sphinx-test-reports: the report parsers, the result vocabulary,
the deterministic case IDs, the `[test_reports]` model of `ubproject.toml`, the
`test-reports` converter that writes a `needs.json`, and the pytest plugin. It is a
**tool, not a Sphinx extension** — nothing to add to `conf.py`, no `Framework :: Sphinx`
classifier. sphinx-test-reports, the extension, depends on it and turns the same reports
into needs inside a build; the dependency never runs the other way. Its documentation is
the "Without Sphinx" section of sphinx-test-reports' site; it has no site of its own.

## Commands

```bash
uv run poe test-ub-test-reports           # the suite (no sphinx axis: it has no Sphinx)
uv run poe import-check-ub-test-reports   # import every module from the built wheel
uv run poe build-ub-test-reports          # sdist + wheel into dist/ub-test-reports
```

## Rules

- **Nothing here may import Sphinx, sphinx-needs or docutils** — not at module level and
  not in a function body, because the converter runs as a build action and the plugin
  inside a test run, and neither has a documentation toolchain. Every environment the
  workspace root produces has Sphinx in it, so the default `.venv` sees only a module-level
  import in the converter's import chain (a subprocess test lists `sys.modules`); a
  function-body import passes there. CI's `toolchain-free` job is the fence — it installs
  the built wheel where the toolchain is absent and runs the whole suite there.
- **`ub-project` is its `ubproject.toml` reader.** Finding, loading and anchoring the file
  come from there (`packages/ub-project/design/reading-contract.md` is the specification);
  what stays here is the `[test_reports]` policy -- keys, types, normalisation, unknown keys
  warned rather than fatal -- and **`TomlConfigError`, the only exception either consumer
  catches**: `load_project_config` re-raises ub-project's `ProjectConfigError` as it, with
  the same message, and it must never be made a subclass of it.
- **The `[test_reports]` model is a parity surface**: ubCode reads the same table and is
  held to the same behaviour. A behaviour change in it — keys, types, normalisation,
  defaults — says so in the changelog, so ubCode can follow.
- **The pytest plugin is opt-in**: `-p ub_test_reports.pytest_plugin`, and no `pytest11`
  entry point — an auto-loaded plugin would change every pytest run in any environment that
  merely has this package installed, the extension's users included. The `pytest` extra's
  floor is fenced by CI's `plugin-floor` job, which runs the suite on the oldest pytest of
  each Python it names.
- **The wire names `sphinxcontrib.test_reports:file` and `sphinxcontrib.test_reports:line`
  must not change.** They are the documented `record_property` names the plugin reserves,
  not an import path, and reports written by older plugins carry them.
- **The test fixtures are this package's own copies** (`tests/fixtures/`), so that its
  suite reads nothing from another member's tree and runs from the installed wheel; some of
  them also exist under sphinx-test-reports' `tests/doc_test/utils/`, where its test
  projects and docs read them. Neither copy ships in an sdist.
- **One plugin test drives an in-process pytest session, and the default `.venv` breaks
  it.** `tests/test_pytest_plugin.py`'s `NESTED` source starts `pytest.main()` inside a
  `pytester` session, where every installed plugin loads; pytest-playwright (the root `js`
  group, in the default `dev` group) refuses the nested soft-assertion scope. So it passes
  `-p no:playwright`, and that line has to stay ONE line: a sibling test builds its own
  source from it by replacing the literal `str(inner)]) == 0`. Run the suite in the default
  `.venv` AND in a cell — green in one proves nothing about the other.
- **Tests build paths with `Path`** and read and write text with an explicit `encoding`, so
  that the suite holds on Windows too.
