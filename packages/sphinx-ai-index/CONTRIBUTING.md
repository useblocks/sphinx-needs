# Contributing

## Development setup

This project uses [Rye](https://rye.astral.sh/) for dependency and environment management.

```bash
git clone https://github.com/useblocks/sphinx-ai-index.git
cd sphinx-ai-index
rye sync
```

## Running tests

We use `tox` to run tests across multiple Python and Sphinx versions.

```bash
rye run tox
```

Or specific testing using pytest explicitly (when activated via `rye shell`):
```bash
pytest
```

The test suite builds a small Sphinx project in a temporary directory and
verifies the generated `ai_docs_index.json`.

## Code style

We rely on automated formatting and static type checking. To run everything at once:

```bash
rye run check
```

Or individual steps manually:

```bash
rye run rye:lint   # ruff check
rye run rye:format # ruff format
rye run mypy:all   # mypy
```

## Releasing

1. Update version in `pyproject.toml`.
2. Update `CHANGELOG.md` with the release notes.
3. Tag the commit: `git tag vX.Y.Z && git push --tags`
4. The [release workflow](.github/workflows/release.yaml) will build the
   wheel and sdist automatically.
5. To publish to PyPI, complete the trusted-publishing setup in the release workflow.
