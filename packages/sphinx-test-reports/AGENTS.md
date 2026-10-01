# AGENTS.md — packages/sphinx-test-reports

The delta for this package. Everything repository-level — the workspace layout, the
commands, the lock, lint/format/type-check configuration, the release recipe, the pull
request requirements — is in the ROOT [`AGENTS.md`](../../AGENTS.md), and this file does not
repeat it. What is here is what an agent has to know that is true of sphinx-test-reports and
not of the workspace.

## Project Overview

sphinx-test-reports is **the Sphinx extension, and only that**: the `test-file`,
`test-suite`, `test-case`, `test-report`, `test-results` and `test-env` directives, which read
JUnit / ctest / googletest XML and tox-envreport JSON and create sphinx-needs items from
them, plus the `tr_link` dynamic function. **Its dependencies are hard** — Sphinx, docutils,
sphinx-needs and `ub-test-reports`. The converter (`test-reports`), the pytest plugin, the
parsers, the result vocabulary, the deterministic IDs and the `[test_reports]` model are
**ub-test-reports** ([`packages/ub-test-reports/`](../ub-test-reports/AGENTS.md)), which
runs without Sphinx and which this package depends on; a change to any of those belongs
there. `[sphinx]` (empty) and `[pytest]` (a pass-through to `ub-test-reports[pytest]`) stay
as extras only so that 2.0.0's install lines keep working until 4.0.

## Package structure

```text
pyproject.toml          # `[project]`, `[project.urls]` and the hatch build tables. NOT
                        #   ruff, ty, pytest or dependency groups: those are the root's,
                        #   and check (7) refuses them here
.readthedocs.yaml       # this package's RTD project; its paths are REPOSITORY-root relative
AUTHORS · LICENSE · README.rst
design/                 # import-commit-map.txt: old hash -> new hash for the 2026-09 import

src/sphinxcontrib/test_reports/   # the pre-3.0 name: four warning aliases, removed in 4.0
src/sphinx_test_reports/
├── __init__.py         # `__version__` FIRST, then the eager `setup` import -- the order is
│                       #   load-bearing: `test_reports` imports `__version__` from here
├── test_reports.py     # the extension entry point: directives, config values, the bridge
│                       #   that applies ub-test-reports' `[test_reports]` model
├── config.py · environment.py · exceptions.py
├── directives/         # one module per directive, all inheriting TestCommonDirective
├── functions/          # `tr_link`, a sphinx-needs dynamic function
├── css/
└── directives/test_report_template.txt   # the DEFAULT tr_report_template -- it SHIPS

tests/                  # `tests/__init__.py` is why this path is not in the root testpaths
docs/                   # conf.py sits IN the source dir; changelog.rst is stamped by `bump`
```

## The things that are true here and nowhere else

### The old import name is four aliases, and nothing else

The package was `sphinxcontrib.test_reports` until 3.0. `src/sphinxcontrib/test_reports/`
keeps exactly four old names working until 4.0: the package as a Sphinx extension, which
warns through Sphinx's logger (type `test_reports.deprecated`) and loads the real extension
with `app.setup_extension`, and `pytest_plugin`, `junitparser` and `jsonparser`, one file
each, which put the REAL module -- `ub_test_reports.<name>`, in the core -- into
`sys.modules` under the old name with one `FutureWarning` per process. **Do not add a finder
or a catch-all**: every other old name is meant to fail as a plain `ImportError`, and
`tests/test_aliases.py` walks BOTH real packages, this one and ub-test-reports, to hold that
-- so a module added to either is covered without anyone remembering the file. **There is no `src/sphinxcontrib/__init__.py`, and there must never be
one**: `sphinxcontrib` is a PEP 420 namespace other distributions install into.

### hatchling, and the fence on the built artefacts

This is the one member that builds with hatchling: its wheel ships two top-level packages,
and flit ships one and drops the other without a word. An editable install reads `src/`, so
a build configuration that lost the aliases would leave every test green. CI's
`toolchain-free` job is therefore where the artefacts are checked -- the job is named for
ub-test-reports, whose suite it runs without Sphinx, and this fence lives there because it
only reads archives. It builds in the release's shape -- the sdist, then the wheel FROM the
sdist, so the sdist's include list bounds what the wheel ships -- and fails when either lacks
a tracked file under `src/`, when the sdist's files outside `src/` are not exactly its
metadata files, or when the wheel's top level is anything but the two packages and its
dist-info, it ships anything under `sphinxcontrib/` but `test_reports/`, or a licence file
other than `LICENSE`. Nothing installs that wheel there: it needs the toolchain, and the
release's compat cell is what walks and tests it. A new top-level package needs a line in
`[tool.hatch.build.targets.wheel]` AND `[tool.hatch.build.targets.sdist]`.

### The suite needs no renderer; the DOCS need two

No test document here carries a rendering directive, so the suite needs neither `java` nor
graphviz's `dot`, and nothing in it copies a jar. (`tests/doc_test/utils/plantuml.jar` used
to sit there, 8.6 MB, and was dead: the three `custom_tr_*` configs pointed at it through
`os.getcwd()`, which under pytest is the rootdir. It left with the import.)

`uv run poe docs-reports` is the opposite case, and among the three EXTENSION packages it
is the only docs build that renders: **13 `needflow` directives** across `filter.rst`, `functions.rst` and
`examples/index.rst`. It needs `java` and `dot` on `PATH`, and it resolves the jar through
the workspace chain — `PLANTUML_JAR`, then the committed `vendor/plantuml/` jar, then a
`plantuml` executable — written out in `docs/conf.py` rather than imported, because a docs
build must not import a test-only member. `.readthedocs.yaml` therefore keeps
`apt_packages: [default-jdk, graphviz]`, where both siblings' deliberately have none.
(sphinx-needs' own docs render far more than this -- 48 needflow directives -- and its
config installs the same two packages; the contrast is with the two sibling EXTENSIONS.)

### `poe test-reports` NAMES its path, and that is not a style choice

The task's command is `pytest tests`, not the `--ignore=` form the sphinx-needs tasks use.
**Eight modules of this package's own source are called `test_*.py`** — `test_reports.py`,
and `directives/test_case.py`, `test_common.py`, `test_env.py`, `test_file.py`,
`test_report.py`, `test_results.py`, `test_suite.py` — so a bare `pytest` from the package
directory collects `src/` and tries to import the extension as a test module.

The cost is poe's documented passthrough behaviour: trailing words are APPENDED, so
`poe test-reports tests/test_cli_convert.py` runs that file *in addition to* the suite rather
than instead of it. `-k` and `-m` behave as expected.

The short name is **`reports`**, not `test-reports`: the naming rule takes the distribution
name minus its `sphinx-` prefix, which here would collide with the task verb and give
`test-test-reports`.

### The old name still appears in the tree, on purpose

Fixture files in `tests/doc_test/utils/` (and their copies under ub-test-reports'
`tests/fixtures/`) carry paths like `file="sphinxcontrib/test_reports/junitparser.py"`:
**test data** describing a historical pytest run, not paths anything opens. The docs' `classname` examples match that data, and
the pytest plugin's reserved `user_properties` names (`sphinxcontrib.test_reports:file`,
`:line`) are documented wire names. None of them is an import path, so none moved with the
package; a rename `sed` over the tree would corrupt them silently.

### `ubproject.toml` is read by ub-test-reports

The `[test_reports]` model -- keys, types, normalisation, `TomlConfigError` -- is
`ub_test_reports.projectconfig`, read through `ub-project`; the core's `AGENTS.md` has its
rules. What is here is the bridge in `test_reports.py` that applies it to the `tr_*` values
at `config-inited`, and `-D` precedence over it.

## Testing

`uv run poe test-reports`, and `test-reports-sphinx7/8/9` for one matrix cell each. No
`--` before pytest arguments — poe forwards it and pytest reads the next word as a path.

The suite spawns Sphinx builds in three places, and all three go through
`sphinx_needs_testkit.sphinx_build_command`, never the bare command resolved on `PATH`.
`tests/test_subprocess_fence.py` is what keeps that true; it reads SOURCE, because a site
that spawns the bare word passes in every environment where `PATH` happens to be right.

**This suite always has Sphinx**, and every test in it may use it: the converter's and the
plugin's tests are ub-test-reports' and run without the toolchain there. A test of a
Sphinx-free module does not belong here — not even split by a marker, which this package no
longer has.

## Releasing

**ub-test-reports releases first.** This package's floor on the core is tight-tracked, so
the core's release pull request (`poe bump ub-test-reports …`) rewrites it, and every
release gate here resolves the core from PyPI: `poe import-check-reports`, the release
plan and the compat cell are red until the core version this tree names is published. The
core's documentation lives on this package's site, so that site's Read the Docs project
must build THIS repository (`packages/sphinx-test-reports/.readthedocs.yaml`) before the
core's first tag — until then its PyPI page links a site with no page about it.

## What the move into this workspace cost, deliberately

Recorded here because none of it is visible in a diff:

- **The sphinx-needs test axis went from five versions to one.** The retired `noxfile.py`
  ran 6.0.1, 6.3.0, 7.0.0, 8.0.0 and 8.5.0; the workspace tests against the sibling in the
  tree, and the published floor narrowed from `>=6.0.1` to `>=8.5.0,<9` with it.
- **Five ruff rule families left**: `FURB`, `PERF`, `PGH`, `PIE`, `SLF`, which this package
  enabled and the root's shared set does not. All five are at zero violations today, which
  is exactly why the loss would otherwise be silent.
- **`plugin_floor`** — the plugin against the oldest pytest of each Python — returned as
  `ci.yaml`'s `plugin-floor` job when the plugin moved to ub-test-reports.
- **mypy left for ty**, with the whole package checked rather than the 15-entry `exclude`
  the mypy configuration carried.
- **Beyond those five families, the root `extend-ignore`s `B904`, `ICN001`, `ISC004` and
  `N818`**, which this package enabled and did not ignore. All four are at zero violations
  today, so it costs nothing now.
- **`linkcheck` retired with no replacement.** The retired CI ran one; the workspace's
  `docs.yaml` is scoped `paths: [packages/sphinx-needs/docs/**]` and runs in that
  directory, so **these docs are link-checked nowhere** -- which is worth knowing given the
  import repointed three stale links. Widening `docs.yaml` is a follow-up, not this import.
- **Three prek hooks retired with it**: `end-of-file-fixer`, `trailing-whitespace` and
  `pretty-format-json`. The root config has no `pre-commit-hooks` repository at all.

The docs still use `sphinx_immaterial` and the vendored `docs/ub_theme/`, where the rest of
the workspace uses furo. Keeping it costs nothing in the lock (sphinx-immaterial is already
there through sphinx-needs' `theme-im` extra); converging is a visible change to a live site
with 41 Read the Docs versions and has an issue of its own.

## History

Imported from `useblocks/sphinx-test-reports` in 2026-09 with its full history, rewritten so
that every historical commit already places its files under `packages/sphinx-test-reports/`.
So `git log <path>` works with **no `--follow`**, and `design/import-commit-map.txt` maps
every old hash to its hash here, for links into the archived old repository.

**The import is not byte-for-byte faithful in exactly one respect**, and the commit map's
header records it: three PlantUML jar blobs (19.97 MB, 94% of the import's weight) were
stripped from every historical tree. A stripped historical checkout still installs, imports
and runs its suite; what it cannot do is render a diagram in a docs build of a 2020-era tree.
