# AGENTS.md

Guidance for AI coding agents working on this repository. It is a
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/). Each distribution
lives under `packages/<distribution-name>/`, and the repository's own tooling is a further,
virtual member in `tools/`. The root is a project named `sphinx-needs-workspace` that is
**never built and never published** (`[tool.uv] package = false`, no `[build-system]`): it
exists to depend on every member, to own the dependency groups they share, and to hold
repository-level policy. **Assume the working directory is the
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
| the repository's own tooling | `tools/` — the workspace fences and the release plan |
| CI | `.github/workflows/`, and `.github/scripts/` for the three checks that must run *inside* a CI environment |
| the docker image | `docker/` — a repository-level deliverable, like the workflows |
| Read the Docs | `.readthedocs.yml`, and it stays at the root under that exact name: the configuration path applies to every version, so moving it makes older tags unbuildable |

**`tools/` is the workspace's tooling — a virtual member, never released, whose manifest
declares the tooling's dependencies; `.github/scripts/` keeps only the checks that must
execute inside a specific CI environment.** The distinction is
what each script *inspects*. `tools/src/sn_tools/` holds the ones that read the manifests
before any environment exists — `check_workspace.py`, `release_plan.py`,
`propagate_floors.py` — plus `import_check.py`, which builds a member's wheel and imports
it in a throwaway environment outside every project one. They are run by path, never
imported (`uv run --no-project --with packaging python tools/src/sn_tools/<script>.py` in
CI for the two CI runs that way — `check_workspace.py` and `release_plan.py` — so a manifest
mistake is named rather than reported as a failed sync; `propagate_floors.py` is the release
engineer's, and CI never runs it). `.github/scripts/` keeps
`check_sphinx_cell.py` (it imports the cell's own sphinx), `check_typing_floor.py` (it runs
inside `.venvs/typing`) and `extract_benchmark_data.py` (it runs inside the benchmark job) —
none of which could move without dragging a member into every matrix cell. `scripts/smoke_needs.py`
stays too: its whole point is to run outside every project environment.

The member is `[tool.uv] package = false`. That makes it **invisible to uv's workspace
selectors**: `uv build --all-packages` skips it, `uv build --package
sphinx-needs-workspace-tools` is refused ("is missing a `build-system`"), the lock records
`source = { virtual = "tools" }`, and `uv sync` installs its *dependencies* without
installing it (`import sn_tools` fails, which is correct — the tooling is run by path). So
nothing in this repository's workflows can build it.

**It is not a build prohibition**: `uv build tools/` (likewise `cd tools && uv build`) does not go through the selector at all
— with no `[build-system]`, PEP 517 says the default backend applies, uv runs
`setuptools.build_meta:__legacy__`, and a real sdist and wheel come out. Two things make the
member unreleasable, and neither is `package = false`:
`tools/src/sn_tools/release_plan.py` refuses a tag that names a virtual member — and since a
tag is the only thing that starts the release workflow, that is the fence, not a
belt-and-braces extra — and the manifest carries `Private :: Do Not Upload`, which PyPI
rejects on upload, for the by-hand path.

## Commands

```bash
uv sync --frozen                      # every member, plus the shared test tooling
uv run poe                            # list every task with its help
uv run poe test-needs -k <expr>       # trailing words are appended to the task's command
uv run poe lint                       # every prek hook over the whole tree
uv run poe typecheck-needs            # ty, against the oldest supported sphinx
uv run poe docs-needs                 # the furo docs build
uv run poe smoke-needs                # build the wheel and test the built package
uv run poe check-workspace            # the manifests agree with each other (Lint runs it)
uv run poe release-plan               # what is pending, in what order (advice; exits 0)
uv run poe import-check-needs         # import the wheel against PyPI-resolved dependencies
uv run --frozen --no-sync pytest tools/tests -q   # the tooling's own tests
UV_PYTHON=3.12 uv run --no-sync poe test-needs-sphinx8   # one CI matrix cell
```

**The root `.python-version` decides which interpreter a bare `uv sync` uses**, and it says
`3.13`. It has to say something, because the default environment's sphinx follows the
interpreter: below Python 3.12 the lock resolves sphinx 8.2, so on such a machine `test-needs`
would quietly be a second sphinx-8 run and CI's "newest sphinx" canary would fail locally.
With the file there, none of that depends on the machine — uv downloads 3.13 if it does not
have it. pyenv reads the same file (asdf and mise only with their legacy / idiomatic
version-file setting enabled), so a pyenv user runs `pyenv install 3.13` once; until then
every pyenv shim reports the version as missing inside this repository. `UV_PYTHON=…`
**overrides** the file (measured: the environment variable wins for both `uv sync` and
`uv run`), which is how the per-cell commands above pick their interpreter, and how CI's
matrix cells do — `setup-uv`'s `python-version` input is documented as setting `UV_PYTHON`.
CI's Lint job (and the monthly `prek-update` job) deliberately pass no such input, so they
run on the pin, and Lint asserts the series it got equals the file.

The machine needs `java` (the plantuml jar is vendored under `tests/doc_test/utils/`) and
graphviz's `dot` on `PATH` — the needflow tests do not skip without them, so install
graphviz as CI does (`apt-get install graphviz`). The browser tests (`-m jstest`, which
`test-needs` excludes) additionally need a browser, and it is not a package: `uv run poe
install-browser` (`playwright install chromium`) fetches one per machine into
`~/.cache/ms-playwright` — `~/Library/Caches/ms-playwright` on macOS, or wherever
`PLAYWRIGHT_BROWSERS_PATH` points, which some prepared images set — measured at ~274 MiB
downloaded, 554 MB on disk, 27 s. It comes from `cdn.playwright.dev` and nothing else on
linux-x64, macOS and Windows: chromium and chrome-headless-shell are Chrome-for-Testing
builds there, and the driver pins that one host for them (`cftUrl` in its `coreBundle.js`),
so the three-mirror `PLAYWRIGHT_CDN_MIRRORS` list — where
`playwright.download.prss.microsoft.com` lives — is only consulted for the linux-arm64
build. A sandbox must allow `cdn.playwright.dev`; once the cache is warm nothing is
fetched, and `uv run poe test-needs-js --browser-channel chrome` drives a Chrome already on
the machine and downloads nothing.

**A browser already on the machine is not necessarily the browser playwright will look
for.** It resolves one exact path, `<cache>/chromium-<revision>/…`, with the revision that
the *pinned* playwright names in its `driver/package/browsers.json`; an image that baked in
a different revision leaves `test-needs-js` erroring `Executable doesn't exist at …`, which
reads like a missing install rather than a mismatch. `uv run poe install-browser` is the
answer; it fetches only what the pin names.

`docs-needs` needs `docs.python.org` and `www.sphinx-doc.org` for intersphinx (and
`api.github.com` for the GitHub-service example, whose warning is suppressed): behind a
proxy that blocks the first two, `-nW` turns the unresolved references into dozens of errors
that look like a docs regression. Run the test suite serially: plantuml is load-sensitive (a
docs or wheel build running alongside it has failed a zero-warnings assertion), and
`-n auto` races on the shared jar copy.

Rough runtimes on a CI-class machine, so you can decide what to background: `lint` 15 s ·
`typecheck-needs` seconds once `.venvs/typing` exists (the first run creates it) ·
`smoke-needs` 6 s · `test-needs-js` 3 s once the browser is installed (9 s cold) · `docs-needs` under
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

**The sdist's contents come from `[tool.flit.sdist]`, not from git.** `uv build` runs
`flit_core.buildapi`, which never consults git: measured, the sdist built in a worktree and
the one built in a `git clone --depth 1` of it have identical entry lists *and* identical
entry sizes. So what decides whether `tests/`, `docs/` and `performance/` ship
is the `include`/`exclude` table in `packages/sphinx-needs/pyproject.toml`, and
`uv run poe smoke-needs` asserts on every run that those trees are in the tarball and that
nothing a docs or test run left behind is. (Until flit 4 this was a worktree hazard rather
than a manifest one: `flit build --use-vcs` tested `.git` for a *directory*, and in a
worktree it is a file, so the sdist silently fell back to the module alone — no warning, a
tenth of the size. Nothing runs `flit` directly any more.)

## Releasing a package

Every distribution under `packages/` releases independently. One workflow,
`.github/workflows/release.yaml`, serves all of them, and the tag says which:
`<dist>-v<version>`. It publishes with PyPI trusted publishing (OIDC), so the
workflow holds no API token, and every one of its checks fails closed.

0. **What is pending, and in what order**: `uv run poe release-plan`. Per publishable
   member it prints the last release tag, what PyPI has, the commits since that tag that
   touched the member's *shipped* code, and — for each dependant — which gate would stop a
   release of it, or the version the compat cell would install from PyPI. Then a suggested
   sequence with the commands. It is advice and exits 0 whatever it finds; the fences are
   still the plan job and the compat cell. For a member with an intra-workspace dependency,
   `uv run python tools/src/sn_tools/import_check.py <dist>` (for sphinx-needs,
   `uv run poe import-check-needs`) installs its freshly built wheel into a throwaway
   environment *outside* this project — so uv resolves the wheel's own dependencies from
   PyPI and every sibling arrives *as published* — and imports every module of it, with
   `--expect-prefix` asserting the imports come from that environment rather than the
   checkout. A missing symbol is named in seconds rather than six minutes into a red compat
   cell.
1. **Release pull request**, from `master` with a clean tree:
   ```bash
   uv version --package <dist> --bump {patch|minor|major} --no-sync
   uv run python tools/src/sn_tools/propagate_floors.py <dist>   # only if a member depends on <dist>
   uv lock
   ```
   `--no-sync` is not optional. `--frozen` leaves `uv.lock` claiming the old version, and
   the `uv-lock` hook then fails a release pull request for a reason that has nothing to do
   with the release; a bare `uv version --bump` creates and syncs `.venv` and re-resolves
   from cold, which reorders `resolution-markers` and stops the diff being readable.
2. **The two numbers `uv version` does not write.** `__version__` in
   `packages/<dist>/src/<module>/__init__.py` (it is stamped into every generated
   `needs.json`, so it is a literal rather than an `importlib.metadata` lookup), and — for
   sphinx-needs — the `NEEDS_VERSION` fallback in `.github/workflows/docker.yaml`, which
   becomes `sphinx-needs-v<version>`: it is used as a git ref, and only the runs with no tag
   of their own read it. `uv run poe check-workspace` fails on the first of them.
3. **Changelog.** Stamp `packages/<dist>/docs/changelog.rst`: the `_release:<version>`
   label, the version heading, `:Released: DD.MM.YYYY`, the `:Full Changelog:` compare link
   (`…/compare/<previous tag>...<dist>-v<version>`) and the summary paragraph. The compare
   link 404s in Docs-Linkcheck until the tag exists; that is expected and not a required
   check.
4. **Check it locally**: `uv run poe lint` (which now runs `check-workspace`) and
   `uv run poe smoke-needs`.
5. **Merge**, then push the tag from `master`:
   ```bash
   git tag <dist>-v<version> && git push origin <dist>-v<version>
   ```
6. The workflow does the rest: validate the tag, build, resolve the built wheel against
   PyPI alone, run the member's suite against its dependencies *as published*, publish, and
   create the GitHub Release titled `<dist> v<version>`. For sphinx-needs it then pushes a
   second, bare `<version>` tag, which is what keeps Read the Docs' `stable`, every
   `git+…@<version>` pin and every existing inbound link working — prefixed tags are not
   PEP 440 and RTD drops what it cannot parse.

**If a job goes red after the publish succeeded** — the GitHub Release step, say — use
**Re-run failed jobs** (`gh run rerun <id> --failed`), never *Re-run all jobs*: a partial
re-run keeps `plan`'s outputs and `build`'s artifact, while a full one fails at `plan`
because the version is on PyPI by then. A red `publish` is the other case and needs nothing
special: nothing was uploaded, so fix the cause and re-run the workflow from the same tag.

**Rehearsing**: `gh workflow run release.yaml -f tag=<dist>-v<version>` runs `plan` and
`build` against `master` and stops there — the publish job is `if: github.event_name ==
'push'`, so a dispatch never publishes. In a rehearsal the "already on PyPI" check becomes
a notice, so the current version is a valid thing to rehearse with.

Never run `uv publish` with its default `dist/*` glob: in a workspace it uploads every
artefact in the directory. Build with `uv build --package <dist> --no-sources -o dist/<dist>`
and publish `dist/<dist>/*`, which is what `release.yaml` and `poe build-needs` both do.

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
