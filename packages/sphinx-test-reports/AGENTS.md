# AGENTS.md — packages/sphinx-test-reports

The delta for this package. Everything repository-level — the workspace layout, the
commands, the lock, lint/format/type-check configuration, the release recipe, the pull
request requirements — is in the ROOT [`AGENTS.md`](../../AGENTS.md), and this file does not
repeat it. What is here is what an agent has to know that is true of sphinx-test-reports and
not of the workspace.

## Project Overview

sphinx-test-reports turns test results into needs. It has **three surfaces, and only one of
them is a Sphinx extension** — which is the single most important thing to know about this
package, because it shapes the manifest, the CI and the split that is coming:

- **the extension** — `test-file`, `test-suite`, `test-case`, `test-report`, `test-results`
  and `test-env` directives, which read JUnit / ctest / googletest XML and tox-envreport
  JSON and create sphinx-needs items from them, plus the `tr_link` dynamic function;
- **the converter** — a `test-reports` console script that turns the same reports into a
  `needs.json` **without running Sphinx at all**;
- **the pytest plugin** — `sphinxcontrib.test_reports.pytest_plugin`, which writes the XML
  shape the extension reads, including per-case properties for traceability.

So **Sphinx and sphinx-needs are an `[project.optional-dependencies]` extra, not
dependencies**: `pip install sphinx-test-reports` gets you `lxml` and the last two surfaces;
`pip install "sphinx-test-reports[sphinx]"` gets you the extension. The published wheel's
`Requires-Dist` is `lxml` alone. Two things in this repository exist because of that — the
`toolchain-free` CI job and this package's `compat-requirements.txt` — and both are
described below.

## Package structure

```text
pyproject.toml          # `[project]`, `[project.urls]`, `[project.scripts]` and
                        #   `[tool.flit.module]`. NOT ruff, ty, pytest or dependency
                        #   groups: those are the root's, and check (7) refuses them here
compat-requirements.txt # released deps the compat cell needs -- see "Releasing" below
.readthedocs.yaml       # this package's RTD project; its paths are REPOSITORY-root relative
AUTHORS · LICENSE · README.rst
design/                 # import-commit-map.txt: old hash -> new hash for the 2026-09 import

src/sphinxcontrib/test_reports/
├── __init__.py         # the lazy `setup` re-export; `sphinxcontrib` is a PEP 420 namespace
├── test_reports.py     # the extension entry point: directives, config values, fields
├── cli.py              # the `test-reports` converter command
├── pytest_plugin.py    # the pytest plugin
├── junitparser.py · jsonparser.py · results.py · identity.py · fields.py
│                       # the toolchain-free core: parsers, the result vocabulary, the
│                       #   deterministic case IDs, the one field table both writers share
├── projectconfig.py    # the `[test_reports]` ubproject.toml model and its discovery walk
├── needs_export.py · remote.py · config.py · environment.py · exceptions.py · toolchain.py
├── directives/         # one module per directive, all inheriting TestCommonDirective
├── functions/          # `tr_link`, a sphinx-needs dynamic function
├── css/ · schemas/JUnit.xsd
└── directives/test_report_template.txt   # the DEFAULT tr_report_template -- it SHIPS

tests/                  # `tests/__init__.py` is why this path is not in the root testpaths
docs/                   # conf.py sits IN the source dir; changelog.rst is stamped by `bump`
```

## The things that are true here and nowhere else

### The module name is DOTTED, and one workspace fence is silent because of it

This package installs into the `sphinxcontrib` PEP 420 namespace, so its import name is
`sphinxcontrib.test_reports` — not the distribution name with `-` → `_`. It says so in
`[tool.flit.module] name`, and three readers honour that key: `check_workspace.Member.module`,
`tools/src/sn_tools/import_check.py`, and (since this package's import) the `module=` step of
`.github/workflows/release.yaml`.

**`check_workspace.py` check (5) prints NO line at all for this member, and that is expected
today.** Every other member gets an `OK … __version__ == <version>` line; this one is absent,
and absence is not something a reader notices — so it is written down here. Two independent
reasons, either of which alone would be enough:

1. `module_version()` joins `member.module` as ONE path component, so it looks for
   `src/sphinxcontrib.test_reports/__init__.py` — a directory that cannot exist. A dotted
   name can never resolve.
2. **This package has no `__version__` literal anywhere.** `check_module_version` treats a
   module without one as "not an error" by design, so even a non-dotted name would print
   nothing until the literal exists. (`test_reports.py` carries a separate, hand-written
   `VERSION = "2.0.0"`, which no gate reads.)

What the gap costs is that `[project] version` and a module literal could drift apart —
which is nil in practice while nothing bumps this member. **Both reasons dissolve together**
when the package is renamed and gains a real `__version__`, which is the release that follows
this import. Until then, do not read check (5)'s silence as a pass.

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

### One test drives an in-process pytest session, and the default environment breaks it

`tests/test_pytest_plugin.py`'s `NESTED` fixture starts a `pytest.main()` *inside* a
`pytester` session. In a developer's default `.venv` that process has every installed plugin
loaded, and **pytest-playwright** — from the root `js` group, which the default `dev` group
includes — keeps a module-global soft-assertion scope, so the nested session dies with
*nested soft assertion scopes are not supported*. Every CI cell syncs
`--no-default-groups --group test --group sphinx-N`, where the plugin is absent. The fixture
therefore passes `-p no:playwright`, and **that line has to stay one line**: a sibling test
builds its own fixture from the same string by replacing the literal `str(inner)]) == 0`.

This is the shape to remember: **run the suite in the default `.venv` AND in a cell.** Green
in one proves nothing about the other.

### `tests/doc_test/utils/*.xml` contain the string `sphinxcontrib/` — leave them alone

Three fixture files carry paths like `file="sphinxcontrib/test_reports/junitparser.py"`.
They are **test data** describing a historical pytest run, not paths anything opens. A
`src/`-move `sed` over the tree would corrupt them silently. `grep -rn 'sphinxcontrib/'` here
finds them; that is expected.

### The `ubproject.toml` discovery boundary inside a monorepo

`projectconfig.find_project_config()` walks UP from the start directory and stops at the
first `ubproject.toml`, else at the project boundary — `.git`, and only where no `.git`
exists anywhere above, `pyproject.toml`. **A `pyproject.toml` on the way up never ends the
walk inside a repository**, deliberately, so a member at `packages/<name>/pyproject.toml`
is understood to sit inside the project whose shared file is at the repository root. So the
behaviour is identical before and after the import. Two consequences: a repository-root
`ubproject.toml` (there is none today) would be picked up by every consumer under
`packages/`, and the boundary tests are unaffected because they build under `tmp_path`,
outside any repository.

## Testing

`uv run poe test-reports`, and `test-reports-sphinx7/8/9` for one matrix cell each. No
`--` before pytest arguments — poe forwards it and pytest reads the next word as a path.

The suite spawns Sphinx builds in three places, and all three go through
`sphinx_needs_testkit.sphinx_build_command`, never the bare command resolved on `PATH`.
`tests/test_subprocess_fence.py` is what keeps that true; it reads SOURCE, because a site
that spawns the bare word passes in every environment where `PATH` happens to be right.

**`toolchain-free` (a CI job in `ci.yaml`, not a cell) is the fence that keeps the converter
and the plugin importable with no documentation toolchain.** It cannot be a `uv sync` cell,
structurally: the root's `[project] dependencies` name every member, those are installed in
every environment, and sphinx-needs declares sphinx at runtime — so every environment this
root can produce has Sphinx in it. The job builds one outside the project with
`uv pip install --no-sources "packages/sphinx-test-reports[pytest]"`, asserts `sphinx`,
`sphinx_needs` and `docutils` are all absent, and runs the ten toolchain-free modules with
`-m "not toolchain"`. The `toolchain` marker itself lives in the ROOT's `markers` list.

## Releasing

`compat-requirements.txt` names `sphinx` and `sphinx-needs`, and unlike both siblings' it
covers the package's **own runtime** requirements rather than a test-only need — because they
are optional. The compat cell installs a bare wheel path with no extras, so without that file
the `import_check` walk fails `6 of 25 modules` on `sphinx_needs` before pytest even starts.

## What the move into this workspace cost, deliberately

Recorded here because none of it is visible in a diff:

- **The sphinx-needs test axis went from five versions to one.** The retired `noxfile.py`
  ran 6.0.1, 6.3.0, 7.0.0, 8.0.0 and 8.5.0; the workspace tests against the sibling in the
  tree, and the published floor narrowed from `>=6.0.1` to `>=8.5.0,<9` with it.
- **Five ruff rule families left**: `FURB`, `PERF`, `PGH`, `PIE`, `SLF`, which this package
  enabled and the root's shared set does not. All five are at zero violations today, which
  is exactly why the loss would otherwise be silent.
- **`plugin_floor`** — the plugin against the oldest pytest of each Python — has no
  replacement yet. It returns with the release that makes the plugin a shipped surface.
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
