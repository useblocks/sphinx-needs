# AGENTS.md

This file provides guidance for AI coding agents working on the
**sphinx-mounts** repository.

## Project Overview

sphinx-mounts is a Sphinx extension that mounts external RST source trees
into a Sphinx build *without copying or symlinking the files*. It is intended
for build systems (Bazel, Buck2, Pants, etc.) that generate documentation
fragments into output directories outside the Sphinx `srcdir`, and for
mono-repo setups where doc bundles are owned by different teams and consumed
by a host doc project.

Key design properties:

- **No staging step**: sources are read in place from their original
  filesystem location. Sphinx's reader opens the absolute external path
  directly.
- **Declarative TOML config is primary**: mount mappings live in
  `ubproject.toml` (default file name, resolved relative to confdir;
  overridable via `mounts_from_toml` in `conf.py`). The TOML schema is a
  top-level `[[mounts]]` array of tables — one block per mount entry.
  The TOML is the source of truth so that IDE plugins, language servers,
  indexers, and build-system integrations written in any language can
  read the mount mapping without evaluating `conf.py`. Shared file
  convention with sibling tools (`[needs]` for sphinx-needs,
  `[codelinks]` for sphinx-codelinks).
- **Legacy `conf.py` fallback**: if no TOML file is present (or
  `mounts_from_toml` is set to `None`), the extension reads
  `mounts = [...]` from `conf.py` instead. When both are present, the
  TOML file wins.
- **Bundle discipline**: each mount source is expected to be a
  self-contained tree — relative links only, no cross-bundle `:ref:`,
  no `..` escapes. The extension does not currently enforce this; a
  separate linter is on the roadmap.

## How It Works

The extension hooks `config-inited`. For each mount, it walks the external
source directory, builds docnames under the configured mount prefix, and
injects them into `app.project._docname_to_path` with **absolute** filesystem
paths. The relevant detail is `pathlib.Path.__truediv__`: when the right
operand is absolute, the left operand is discarded. So when Sphinx later
calls `Project.doc2path(docname, absolute=True)` and computes
`srcdir / stored_path`, the stored absolute path wins and Sphinx reads from
the external location transparently.

## Repository Structure

```text
pyproject.toml          # Project configuration and dependencies
tox.ini                 # Tox test environment configuration
README.md               # Project README
LICENSE                 # MIT License

src/sphinx_mounts/
├── __init__.py         # Package init with Sphinx setup() entry point
├── extension.py        # Sphinx event handlers, including the TOML loader
├── config.py           # MountConfig dataclass, hand-rolled validation,
│                       # and the TOML loader for the `mounts` config
└── mounter.py          # Core logic — discovers external files and
                        # injects them into app.project

tests/
├── conftest.py         # Pytest fixtures and Sphinx test harness
├── test_config.py      # Tests for config validation
├── test_mounting.py    # Tests for end-to-end mounting
├── test_bazel.py       # Bazel integration test (marker: bazel)
└── fixtures/
    ├── bundle_simple/  # A simple self-contained RST bundle
    ├── bundle_nested/  # A bundle with nested subdirectories
    ├── host_project/   # A minimal Sphinx project that mounts the bundles
    └── bazel/          # A self-contained Bazel workspace

docs/                   # Documentation source (RST)
├── conf.py             # Sphinx configuration
├── ubproject.toml      # Declarative metadata for the ubCode language
│                       # server and other static readers (schema +
│                       # `index_on_save = true`)
└── source/
    ├── index.rst       # Documentation index
    ├── motivation.rst
    ├── installation.rst
    ├── configuration.rst
    ├── usage.rst
    ├── integration.rst
    ├── bazel.rst
    └── changelog.rst
```

## Development Commands

All commands should be run via [`tox`](https://tox.wiki) for consistency.

### Testing

```bash
# Run default test environment (skips Bazel tests)
tox

# Run a specific tox environment
tox -e py312-sphinx9

# Run Bazel integration tests (requires bazel on PATH)
tox -e bazel

# Run a specific test
tox -e py312-sphinx9 -- tests/test_mounting.py::test_basic_mount
```

### Documentation

```bash
tox -e docs-clean
tox -e docs-update
tox -e docs-live
```

### Code Quality

```bash
tox -e ty
tox -e ruff-check
tox -e ruff-fmt
uv run prek run --all-files
```

## Code Style Guidelines

- **Formatter/Linter**: Ruff (configured in `pyproject.toml`)
- **Type Checking**: [ty](https://github.com/astral-sh/ty) (Astral's fast
  Python type checker, written in Rust). Run via `tox -e ty`.
- **Prek**: Use prek (drop-in pre-commit replacement) for consistent code style

### Best Practices

- **Type annotations**: Use complete type annotations for all function
  signatures. Use frozen :func:`dataclasses.dataclass` for configuration
  data structures, with validation in ``__post_init__`` and ``from_dict``
  classmethods for dict input. No pydantic or other heavyweight schema
  dependency — the surface area is small enough to validate by hand.
- **Docstrings**: Use Sphinx-style docstrings
  (`:param:`, `:return:`, `:raises:`). Types belong in type hints, not in
  docstrings.
- **Immutability**: Prefer immutable data structures. Configuration
  dataclasses use ``frozen=True, slots=True``.
- **Internal access discipline**: This extension intentionally reads and
  writes `sphinx.project.Project._docname_to_path`. Any use of Sphinx
  private attributes is gated to `src/sphinx_mounts/mounter.py` and called
  out in a comment that names the upstream code being relied on.

## Documentation Style (RST)

- **No nested inline markup.** RST does not support inline markup
  nesting. Specifically, never put an inline literal (double-backtick
  span) inside strong (`**...**`) or emphasis (`*...*`). The outer
  delimiters render as raw asterisks rather than bold/italic, e.g.

  ```rst
  the **legacy ``conf.py`` fallback**     <- BROKEN, ``**`` shown raw
  the legacy ``conf.py`` fallback         <- OK, drop the strong wrapper
  the **legacy conf.py fallback**         <- OK, drop the literal
  ```

  The inline code is already visually distinct, so dropping the strong
  wrapper is usually the right fix. The same restriction applies to any
  combination of `**`, `*`, and double-backticks inside one another.
  When in doubt, build the docs (`tox -e docs-update`) and check the
  rendered HTML.

## Testing Guidelines

- Tests use `pytest` with `sphinx.testing.fixtures`.
- Bazel integration tests live in `tests/test_bazel.py` and are marked with
  `@pytest.mark.bazel`. They skip when `bazel` is not on `PATH`.
- Fixture bundles in `tests/fixtures/` are checked-in static RST trees;
  they are not generated.

## Commit Message Format

Use this format:

```text
<EMOJI> <KEYWORD>: Summarize in 72 chars or less (#<PR>)

Optional detailed explanation.
```

Keywords:

- `✨ NEW:` – New feature
- `🐛 FIX:` – Bug fix
- `👌 IMPROVE:` – Improvement (no breaking changes)
- `‼️ BREAKING:` – Breaking change
- `📚 DOCS:` – Documentation
- `🔧 MAINTAIN:` – Maintenance changes only
- `🧪 TEST:` – Tests or CI changes only
- `♻️ REFACTOR:` – Refactoring

## Pull Request Requirements

1. **Description**: A meaningful description of the change.
2. **Tests**: Test cases for new functionality or bug fixes.
3. **Documentation**: Update `docs/source/` if behavior changes.
4. **Changelog**: Update `docs/source/changelog.rst`.
5. **Code Quality**: `uv run prek run --all-files` must pass.

## Local-Only Files (Do Not Commit)

`docs/superpowers/` is a gitignored workspace for AI agent workflow
artifacts — specs, implementation plans, and other scratch documents
produced by the Superpowers / brainstorming / writing-plans skills.
These files are local to a contributor's checkout and **must never be
committed**. The directory is in `.gitignore`; do not override the
ignore via `git add -f` or commit individual files under it.

## Reference Documentation

- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [Sphinx Project class](https://github.com/sphinx-doc/sphinx/blob/master/sphinx/project.py)
  — the upstream class whose internals this extension reads and writes.
- [Bazel](https://bazel.build/)
