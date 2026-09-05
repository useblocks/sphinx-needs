# AGENTS.md — packages/sphinx-mounts

The delta for this package. Everything repository-level — the workspace layout, the
commands, the lock, lint/format/type-check configuration, the release recipe, the pull
request requirements — is in the ROOT [`AGENTS.md`](../../AGENTS.md), and this file does
not repeat it. What is here is what an agent has to know that is true of sphinx-mounts and
not of the workspace.

## Project Overview

sphinx-mounts is a Sphinx extension that mounts external RST/Markdown source trees into a
Sphinx build *without copying or symlinking the files*. It is aimed at build systems
(Bazel, Buck2, Pants) that generate documentation fragments into output directories outside
the Sphinx `srcdir`, and at monorepos where doc bundles are owned by different teams and
consumed by a host doc project.

Key design properties:

- **No staging step**: sources are read in place from their original filesystem location.
  Sphinx's reader opens the absolute external path directly.
- **Declarative TOML config is primary**: mount mappings live in `ubproject.toml` (default
  file name, resolved relative to confdir; overridable via `mounts_from_toml` in
  `conf.py`). The schema is a top-level `[[mounts]]` array of tables — one block per mount
  entry. The TOML is the source of truth so that IDE plugins, language servers, indexers
  and build-system integrations written in any language can read the mount mapping without
  evaluating `conf.py`. Same file convention as its sibling tools (`[needs]` for
  sphinx-needs, `[codelinks]` for sphinx-codelinks).
- **Legacy `conf.py` fallback**: with no TOML file present (or `mounts_from_toml = None`),
  the extension reads `mounts = [...]` from `conf.py`. When both are present, TOML wins.
- **Bundle discipline**: each mount source is expected to be a self-contained tree —
  relative links only, no cross-bundle `:ref:`, no `..` escapes. The extension does not
  enforce all of this; `path_check` enforces the escape half.

## How It Works

The extension hooks `config-inited`. For each mount it walks the external source directory,
builds docnames under the configured mount prefix, and injects them into
`app.project._docname_to_path` with **absolute** filesystem paths. The relevant detail is
`pathlib.Path.__truediv__`: when the right operand is absolute, the left operand is
discarded. So when Sphinx later calls `Project.doc2path(docname, absolute=True)` and
computes `srcdir / stored_path`, the stored absolute path wins and Sphinx reads from the
external location transparently.

## Package Structure

```text
pyproject.toml          # `[project]` and `[build-system]` ONLY -- see below
README.md · LICENSE
compat-requirements.txt # released deps the suite needs, for release.yaml's compat cell
.readthedocs.yaml       # this package's RTD config; its paths are REPOSITORY-root relative

src/sphinx_mounts/
├── __init__.py         # package init with the Sphinx setup() entry point
├── extension.py        # Sphinx event handlers, including the TOML loader
├── config.py           # MountConfig dataclass, hand-rolled validation
├── dialect.py          # the variant-condition dialect
├── logging.py          # typed `mounts.*` warning helpers (suppress_warnings)
├── warnings.py         # warning topics
└── mounter.py          # core logic -- discovers external files and injects them

tests/
├── conftest.py         # pytest fixtures and the Sphinx test harness
├── test_*.py           # one module per area; `test_bazel.py` and part of
│                       #   `test_example.py` carry the `bazel` marker
├── example/            # the checked-in end-to-end Bazel example (see below)
└── fixtures/           # checked-in static bundles, plus the vendored conformance corpus

docs/                   # conf.py BESIDE its sources -- see "Documentation" below
design/                 # mapping-contract.md, and the import commit map
```

**The manifest carries `[project]` and `[build-system]` and nothing else.** No
`[dependency-groups]`, no `[tool.ruff]`, no `[tool.pytest.ini_options]`, no `[tool.ty]`:
those are the workspace root's, and `tools/src/sn_tools/check_workspace.py` check (7)
refuses them here. A `[tool.ruff]` table in this file would not extend the root's ruleset —
ruff resolves configuration per file by walking up to the nearest `pyproject.toml` that has
one, so it would silently *replace* it for every file in this package.

## Commands

All from the repository root, all through poe (there is no `tox.ini` any more):

```bash
uv run poe test-mounts                 # the suite, `-m 'not bazel'`
uv run poe test-mounts-bazel           # only the bazel-marked tests
uv run poe test-mounts-sphinx7         # one matrix cell (UV_PYTHON picks the interpreter)
uv run poe docs-mounts                 # the furo docs build, -nW
uv run poe typecheck                   # ty, over both packages, against the sphinx floor
uv run poe import-check-mounts         # import every module from the built wheel
```

A path passed to a package task is relative to `packages/sphinx-mounts`.

## Documentation

`docs/conf.py` sits **beside** its sources in `docs/`, not above them in `docs/source/`.
That is not cosmetic: Read the Docs names a `conf.py` and then runs sphinx with that file's
own directory as the source directory, with no `-c` — so the split layout this package used
as a standalone repository cannot be built there at all. Do not reintroduce it.

### Documentation Style (RST)

- **No nested inline markup.** RST does not support inline markup nesting. Specifically,
  never put an inline literal (double-backtick span) inside strong (`**...**`) or emphasis
  (`*...*`). The outer delimiters render as raw asterisks rather than bold/italic:

  ```rst
  the **legacy ``conf.py`` fallback**     <- BROKEN, ``**`` shown raw
  the legacy ``conf.py`` fallback         <- OK, drop the strong wrapper
  the **legacy conf.py fallback**         <- OK, drop the literal
  ```

  The inline code is already visually distinct, so dropping the strong wrapper is usually
  the right fix. When in doubt, build the docs and read the rendered HTML.

## Testing Guidelines

- Tests use `pytest` with `sphinx.testing.fixtures`.
- **Renderers are a prerequisite, not an optional extra.** The graphviz and PlantUML cases
  in `tests/test_path_directives.py` render for real, and `_require_renderer` **asserts**
  rather than skipping — the point of those tests is to exercise the whole mounts chain
  including the render step. Two routes, and either satisfies them:
  - `dot` (graphviz) on `PATH`, which is required and has no alternative; and
  - PlantUML, from **either** a `plantuml` executable on `PATH` **or** a plantuml jar named
    by `PLANTUML_JAR`, with `java` on `PATH`. The second is what CI uses: no runner image
    has a `plantuml` package, so `ci.yaml` and `release.yaml` point the variable at
    `packages/sphinx-needs/tests/doc_test/utils/plantuml.jar`, which that package vendors
    for its own tests. Locally:
    `PLANTUML_JAR=$PWD/packages/sphinx-needs/tests/doc_test/utils/plantuml.jar uv run poe test-mounts`.

  Mermaid uses `raw` output, so no `mmdc` binary is needed.
- **The three sphinx-needs integration tests assert rather than skip too.** They are the
  only coverage of that integration, and they exist for the release workflow's compat cell,
  which runs this suite against the dependencies as PUBLISHED. sphinx-needs is a test-only
  dependency, so it reaches that cell only through `compat-requirements.txt`; the assertion
  is what makes that file load-bearing. In the workspace it is a sibling member and always
  installed.
- **Bazel tests** live in `tests/test_bazel.py` and `tests/test_example.py`, carry
  `@pytest.mark.bazel`, and skip when no `bazel`/`bazelisk` is on `PATH`. They are
  deselected from the ordinary cells and run in CI's own `bazel` lane, which also builds
  the three targets `tests/example/README.md` documents. The two wrappers under
  `tests/example/` (`build_docs.sh`, `build_docs_sandbox.sh`) run `uv run --project` against
  the WORKSPACE ROOT, four levels up — dependency groups belong to the root in a uv
  workspace, so pointing them at this member would install the member and nothing else.
- **The vendored conformance corpus.** `tests/fixtures/variant_condition_conformance.toml`
  is shared byte-for-byte with ubCode, which is its repository of record: do not reformat
  it, do not edit its prose, and treat a change to it as owing a re-sync pull request there.
  `.gitattributes` pins its line endings and the taplo hook excludes it, exactly as the
  needflow conformance corpus under `packages/sphinx-needs` is protected.
  `test_variant_conditions.py` asserts the case COUNT, so a trimmed vendor is a red test
  rather than reduced coverage.
- Fixture bundles in `tests/fixtures/` are checked-in static trees; they are not generated.
- Two mount modes, two code paths: `_attach_mount_dir` and `_attach_mount_files` differ in
  docname derivation, in dotfile handling, and in how the bundle root is computed. A
  behaviour change to one usually needs a test for the other.

## Code Style

The root owns the formatter, the linter and the type checker. What is specific here:

- **Type annotations**: complete annotations on every signature. Frozen
  `dataclasses.dataclass` for configuration data, with validation in `__post_init__` and
  `from_dict` classmethods for dict input. No pydantic — the surface area is small enough
  to validate by hand.
- **Docstrings**: Sphinx-style (`:param:`, `:return:`, `:raises:`). Types belong in the
  hints, not in the docstring.
- **Immutability**: prefer immutable data structures; the configuration dataclasses are
  `frozen=True, slots=True`.
- **Internal access discipline**: this extension deliberately reads and writes
  `sphinx.project.Project._docname_to_path`. Every use of a Sphinx private attribute is
  confined to `src/sphinx_mounts/mounter.py` and carries a comment naming the upstream code
  it relies on.
- **The sphinx floor is real.** The `typing` group pins the oldest supported sphinx, and
  ty checks against it; annotations that only hold on the newest sphinx are caught there
  (that is how `_MountAwareProject.__init__`'s `srcdir` annotation was found on import).

## Local-only files (do not commit)

`docs/superpowers/` is a gitignored workspace for AI agent workflow artefacts — specs,
implementation plans, scratch documents. The directory is in the root `.gitignore`; do not
override it with `git add -f` or commit individual files under it.

## Reference documentation

- [Sphinx](https://www.sphinx-doc.org/)
- [Sphinx `Project` class](https://github.com/sphinx-doc/sphinx/blob/master/sphinx/project.py)
  — the upstream class whose internals this extension reads and writes.
- [Bazel](https://bazel.build/)

## History

This package was imported from `useblocks/sphinx-mounts` in 2026-09 with its full history,
rewritten so that every historical commit already places its files under
`packages/sphinx-mounts/`. So `git log <path>` works with no `--follow` — unlike the
sphinx-needs files, which the workspace restructure moved. `design/import-commit-map.txt`
maps every old hash to its hash here, for links into the archived old repository.
