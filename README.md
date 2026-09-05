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
