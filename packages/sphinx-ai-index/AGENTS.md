# AGENTS.md — packages/sphinx-ai-index

The delta for this package. Everything repository-level — the workspace layout, the
commands, the lock, lint/format/type-check configuration, the release recipe, the pull
request requirements — is in the ROOT [`AGENTS.md`](../../AGENTS.md), and this file does
not repeat it.

## What it is

A Sphinx extension that writes `ai_docs_index.json` into the HTML output directory: one
entry per page, with its source and HTML paths, its title, its top-level section titles
and an optional summary taken from the `.. page-summary::` directive (which renders
nothing). Its reader of record is ubCode — the `ubc_docs` crate builds the page catalog
of its documentation search from a published site's copy of this file.

## The JSON is a contract

What the file contains, when it is written, and what ubCode does with each field (including
the values that make it drop a page) is pinned in
[`design/json-contract.md`](design/json-contract.md). A change to `on_build_finished`'s
output, or to when it writes, is a change to that file first — and, for anything but a new
field, to ubCode alongside. The format's own `"version"` is not the package version.

## Where it runs

Every `sphinx-*` docs site in this repository loads it, so each publishes an index. In CI
the docs environments install it from the workspace like any member; on Read the Docs each
site's config pip-installs `packages/sphinx-ai-index` from the checkout before the package
it documents, so the sites always build with the copy beside them, and a pull request that
touches only this package still rebuilds them.

## Manifest

`[project]` and `[build-system]` only, like every member: no `[dependency-groups]`,
`[tool.ruff]`, `[tool.pytest]` or `[tool.ty]` — `check_workspace.py` check (7) refuses them.
`__version__` in `src/sphinx_ai_index/__init__.py` is the version `setup()` reports to
Sphinx, and check (5) holds it equal to `[project] version`; `poe bump` stamps both.

## Tests

`uv run poe test-ai-index` (paths relative to this package). The suite builds small Sphinx
projects in `tmp_path` with `sphinx.application.Sphinx` directly and needs no renderer, no
git, no libclang and no network. Its property-based tests need `hypothesis`, which comes
from the root `test` group, which is also how the release workflow's compat cell gets it, and it
writes its example database into the working directory (`.hypothesis/`, ignored at the
root).

## History

Imported from `useblocks/sphinx-ai-index` in 2026-10 with its full history, rewritten so
that every historical commit already places its files under `packages/sphinx-ai-index/`;
`git log <path>` needs no `--follow`. `design/import-commit-map.txt` maps the old hashes to
the new ones, and the old `v0.1.0` tag is `sphinx-ai-index-v0.1.0` here.
