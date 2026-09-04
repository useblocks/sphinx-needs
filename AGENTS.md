# AGENTS.md

Guidance for AI coding agents working on this repository. It is a
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/). Each distribution
lives under `packages/<distribution-name>/`. The root is a project named
`sphinx-needs-workspace` that is **never built and never published** (`[tool.uv] package =
false`, no `[build-system]`): it exists to depend on every member, to own the dependency
groups they share, and to hold repository-level policy. **Assume the working directory is the
repository root**; every command below is written for it.

Each package has its own `AGENTS.md` with the detail for that package — start with
[`packages/sphinx-needs/AGENTS.md`](packages/sphinx-needs/AGENTS.md), which carries the
extension's architecture. The `CLAUDE.md` next to each `AGENTS.md` is a one-line shim that
imports it (Claude Code reads `CLAUDE.md`, not `AGENTS.md`): edit the `AGENTS.md`, never
the shim.

## Where things are

| what you are changing | where it lives |
|---|---|
| the extension's behaviour | `packages/sphinx-needs/src/sphinx_needs/` |
| its tests | `packages/sphinx-needs/tests/` |
| its documentation | `packages/sphinx-needs/docs/` (changelog: `docs/changelog.rst`) |
| the needflow conformance corpus | `packages/sphinx-needs/tests/conformance/` — shared byte-for-byte with ubCode, which is its repository of record; do not reformat it (`.gitattributes` and the yamlfmt exclude protect it) |
| a package's metadata, dependencies and extras | `packages/<pkg>/pyproject.toml` |
| dependency groups (`test`, `benchmark`, `sphinx-7/8/9`, `typing`) | the root `pyproject.toml` — they are shared, and a group cannot be composed across the root/member boundary |
| lint, format, type-check, pytest and task configuration | the root `pyproject.toml` |
| the lock | the root `uv.lock` — one lock for the whole workspace |
| hooks | the root `.pre-commit-config.yaml` — one config; anything triggered by `uv.lock` has to live here |
| CI, scripts | `.github/` |
| the docker image | `docker/` — a repository-level deliverable, like the workflows |
| Read the Docs | `.readthedocs.yml`, and it stays at the root under that exact name: the configuration path applies to every version, so moving it makes older tags unbuildable |

## Commands

```bash
uv sync --frozen                      # every member, plus the shared test tooling
uv run poe                            # list every task with its help
uv run poe test-needs -k <expr>       # trailing words are appended to the task's command
uv run poe lint                       # every prek hook over the whole tree
uv run poe typecheck-needs            # ty, against the oldest supported sphinx
uv run poe docs-needs                 # the furo docs build
uv run poe smoke-needs                # build the wheel and test the built package
UV_PYTHON=3.12 uv run --no-sync poe test-needs-sphinx8   # one CI matrix cell
```

**The default environment's sphinx follows whichever interpreter uv picks.** Below Python
3.12 the lock resolves sphinx 8.2, so a bare `uv sync` on such a machine makes `test-needs`
a second sphinx-8 run, skips the 3.12-gated tests, and fails CI's "newest sphinx" canary
locally. Export `UV_PYTHON=3.12` (or newer) before `uv sync` to get the cell CI expects;
the per-cell `UV_PYTHON=…` in the commands above still overrides it.

The machine needs `java` (the plantuml jar is vendored under `tests/doc_test/utils/`) and
graphviz's `dot` on `PATH` — the needflow tests do not skip without them, so install
graphviz as CI does (`apt-get install graphviz`). The Cypress tests (`-m jstest`, which
`test-needs` excludes) additionally need Node and `npm install cypress`, run in
`packages/sphinx-needs` where the `package.json` is: its postinstall fetches a ~250 MB
binary from `download.cypress.io`, which redirects to `cdn.cypress.io`, into the per-machine
cache `~/.cache/Cypress/<version>/` — a sandbox must allow both hosts, and once that cache
is warm the install needs neither. `docs-needs` needs `docs.python.org` and
`www.sphinx-doc.org` for intersphinx (and `api.github.com` for the GitHub-service example,
whose warning is suppressed): behind a proxy that blocks the first two, `-nW` turns the
unresolved references into dozens of errors that look like a docs regression. Run the test
suite serially: plantuml
is load-sensitive (a docs or wheel build running alongside it has failed a zero-warnings
assertion), and `-n auto` races on the shared jar copy.

Rough runtimes on a CI-class machine, so you can decide what to background: `lint` 15 s ·
`typecheck-needs` seconds once `.venvs/typing` exists (the first run creates it) ·
`smoke-needs` 6 s · `test-needs-js` 20 s once cypress is installed · `docs-needs` under
2 min · `test-needs` 7–8 min serial · `benchmark-needs` 4 min. `docs-needs` runs with `--keep-going`, so it prints every warning
and then exits 1 — do not read a full log as success. `benchmark-needs` is currently red
(12 failures in `tests/benchmarks/test_querying.py`: the test mocks `NeedsSphinxConfig`
with a spec, which lacks the dynamically assigned `variant_data_proxy` — #1840, unrelated
to the layout); CI runs only its `_time` and `_memory` subsets, which pass.

**Naming rule:** a task that acts on the whole repository is bare (`lint`); a task that
acts on one package ends in that package's short name — the distribution name minus its
`sphinx-` prefix (`test-needs`, `docs-needs`, `typecheck-needs`).

ty reads the root `[tool.ty]` from any directory in the tree, because it walks up for a
`pyproject.toml` and the package has no `[tool.ty]` of its own — so
`cd packages/sphinx-needs && ty check`, `ty check packages/sphinx-needs` and an editor
opened anywhere all give the gate's result. `ty` itself lives only in the `typing`
environment — `.venvs/typing/bin/ty`, created by the first `uv run poe typecheck-needs` —
not in `.venv` and not on `PATH`.

**Some tests are gated to one interpreter** — `grep -rn 'skipif.*version_info' packages/*/tests`
finds them (today: the schema snapshot test, Python 3.12 only). A default run skips them
silently, so anything touching test infrastructure or a package path has to be run on the
gating interpreter too: `UV_PYTHON=3.12 uv run --no-sync poe test-needs-sphinx9 tests/schema`.

Package tasks run with the package as their working directory, so **a path you pass to
one is relative to `packages/sphinx-needs`** — `uv run poe test-needs tests/test_basic_doc.py`,
not the repository-relative path. (`testpaths` is only honoured when pytest is invoked from
the rootdir, so the tasks carry `--ignore=performance` instead of naming `tests`: a path in
the task's own command would be *added* to yours rather than replaced by it.)

`uv sync` with no arguments is enough: the root's default `dev` group includes the shared
`test` group, and the root depends on every member. The `sphinx-7`, `sphinx-8`, `sphinx-9`
and `typing` groups are the workspace's one test matrix and one type-checking floor, and all
four sit in the ONE `[tool.uv] conflicts` set in the root `pyproject.toml`, qualified with
`package = "sphinx-needs-workspace"`. That set is also the alignment fence: a member whose own
sphinx range excludes one of those pins makes `uv lock` fail rather than quietly skip a cell.
The root's name exists for exactly this — in a workspace uv requires a `package =` on every
conflict entry, and a nameless root has none to give.

Extras are the member's, but `--extra` resolves against the root, so the root re-exports each
one (`docs = ["sphinx-needs[docs]"]`). A new extra on a member needs a line there too.

## Incantations that do NOT work here

```bash
uv sync --all-groups             # always fails: the sphinx matrix groups are conflicting
uv sync --package sphinx-needs   # makes the MEMBER the project, so none of the root's groups
                                 #   are installed -- no pytest, no poe, no prek
cd packages/sphinx-needs && uv sync         # same effect: installs the member and nothing
                                 #   else. The test tooling is the root's; sync from the root
cd packages/sphinx-needs && uv run pytest   # testpaths is ignored when cwd != rootdir;
                                 #   collects performance/ and errors. Pass `tests`, or
                                 #   `--ignore=performance` as the poe tasks do
uv build                         # at the root, setuptools tries a flat-layout build of the
                                 #   whole repository and fails. Name the package
                                 #   (`uv build packages/sphinx-needs`) or use
                                 #   `uv build --all-packages`, which skips the root
uv pip install|uninstall …       # NOT project-scoped: it targets the activated virtualenv,
                                 #   whatever UV_PROJECT_ENVIRONMENT says. Pass --python
```

**Never build a release or an sdist from a git worktree.** In a worktree `.git` is a file,
flit's VCS detection tests for a directory, and `flit build --use-vcs` then silently falls
back to a module-only sdist — no warning, a tenth of the size. Use a real clone.

## History after the directory move

Files moved in 2026-09, so `git log <path>` — which is what GitHub's per-file *History*
button runs — shows only the commits since. Use `git log --follow <path>` for the full
history (`git blame` follows renames on its own and needs nothing), and
`git log --first-parent` to read the squash-merged mainline.

To rebase a pull request opened before the move, use
`git rebase -X find-renames=15% origin/master`, and never `git rebase --apply`, `git am`
or a downloaded `.patch` — those do no rename detection at all. The full recipe is in the
move's pull request.

## Pull request requirements

1. **Description**: a meaningful description or link explaining the change
2. **Tests**: test cases for new functionality or bug fixes
3. **Documentation**: update the docs if behaviour changes or options are added
4. **Changelog**: update `packages/sphinx-needs/docs/changelog.rst`
5. **Code quality**: `uv run poe lint` and `uv run poe typecheck-needs` pass

## Issues and labels

Every issue and pull request carries one or more `pkg:` labels naming what it concerns:
`pkg: <distribution>` (today `pkg: sphinx-needs`) or `pkg: workspace` for the repository
itself — workflows, CI, release, docker, tooling, the workspace root. Pull requests get
theirs automatically from the paths they touch (`.github/labeler.yml`); the issue forms
set it from their "Package" dropdown (`.github/issue-labeler.yml`). **An issue created
without a form — `gh issue create`, the API, a blank web issue — gets no label from
anywhere, so pass it yourself**, together with the kind (`bug`, `enhancement`,
`documentation`): `gh issue create --label 'pkg: sphinx-needs' --label bug --title …
--body-file …`. Templates never constrain the API; they only shape the web "New issue"
page and the interactive `gh issue create` prompt. Triage adds the label to whatever
arrives without one.
