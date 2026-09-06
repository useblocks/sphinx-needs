# sphinx-needs

This repository is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/):
one package per distribution under `packages/`, and a root that is never built or published.
The root depends on every package, owns the dependency groups they share, and holds
repository-level policy — the lock file, the lint and type-check configuration, the task
definitions and the CI workflows.

| package | distribution | what it is |
|---|---|---|
| [`packages/sphinx-needs`](packages/sphinx-needs) | [`sphinx-needs`](https://pypi.org/project/sphinx-needs/) | the Sphinx extension for managing requirements and specifications — [documentation](https://sphinx-needs.readthedocs.io), [README](packages/sphinx-needs/README.rst) |
| [`packages/sphinx-mounts`](packages/sphinx-mounts) | [`sphinx-mounts`](https://pypi.org/project/sphinx-mounts/) | the Sphinx extension that mounts external source trees into a build without copying or symlinking — [documentation](https://sphinx-mounts.useblocks.com), [README](packages/sphinx-mounts/README.md) |

## Why one repository, and why still several packages

The question comes up, so here is the reasoning. The proposal and its discussion are in
[#1803](https://github.com/useblocks/sphinx-needs/discussions/1803).

One repository, because the extensions are developed against sphinx-needs as it is *now*:
a change to sphinx-needs and the extension change it calls for land together, tested
against each other at the same commit, with one lock file, one CI, one lint and typing
configuration and one issue tracker.

Still one distribution per package, and not one `sphinx-needs` with an extra per feature,
because:

- **An install is whole or absent.** An extension's dependencies — parser grammars, a
  libclang binding, a build tool — land only on the people who asked for that extension,
  and never half-present on everyone else.
- **A Python extra is not a feature flag.** It is a set of additional requirements, and
  nothing records that it was requested; a bundled feature has to probe its own imports at
  run time, in its `setup()`, its console scripts and its type checking, and a user who
  later uninstalls the dependency finds out at build time. sphinx-needs pays that once, for
  matplotlib, and does not want to pay it per extension. A distribution boundary is
  resolved by the installer, visible to the type checker and versioned.
- **Each package keeps its own version and cadence.** An extension can change its
  interface without a sphinx-needs major release, and ship a fix without waiting for the
  next sphinx-needs release.
- **Not every package depends on sphinx-needs.** sphinx-mounts does not, and an
  extension's analysis engine or command line can be useful without it.

The coupling that remains is a policy, and tooling keeps it honest: a package that depends
on sphinx-needs requires the current release as its floor and caps at the next major (the
workspace check enforces the range), the release workflow tests every built wheel against
its siblings *as published*, and `uv run poe release-plan` says what is pending and in
which order.

## Working here

Two commands are enough to get started, from this directory:

```bash
uv sync --frozen   # every package, plus the shared development and test dependencies
uv run poe         # list every task, with its help
```

No group has to be named: the test tooling is a group of the workspace root, and the root's
default `dev` group includes it.

Tasks that act on the whole repository are named plainly (`lint`); tasks that act on one
package end in that package's short name (`test-needs`, `docs-needs`, `docs-mounts`).

Contributions are very welcome — see
[the contributing guide](packages/sphinx-needs/docs/contributing.rst), and `AGENTS.md` for
the repository's layout in more detail (`CLAUDE.md` only imports it).
