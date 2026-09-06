# `vendor/plantuml/`

The workspace's PlantUML renderer: **one** jar, at **one** pinned version, **committed here**,
for every package in this repository. `pin.toml` names the version and its sha256;
`plantuml-<version>.jar` beside it is that file. Nothing downloads it — a checkout has it.

Everything that renders a diagram in this repository reads this one pin — sphinx-needs' test
suite (`tests/conftest.py`) and its documentation (`docs/conf.py`), the performance project,
the sphinx-mounts suite (through `PLANTUML_JAR`, which CI and the poe tasks set from here),
`ci.yaml`, `release.yaml`, `benchmark.yaml`, `docs.yaml` and Read the Docs. The docker image
is the one exception it cannot be: a `Dockerfile` cannot read TOML, so `docker/Dockerfile`
repeats the version in an `ARG` and says so.

## Why one committed jar, here

Until this directory existed the repository carried **two** jars at **two** versions —
one under `packages/sphinx-needs/tests/doc_test/utils/` (PlantUML 1.2022.5, for the tests)
and one under `packages/sphinx-needs/docs/utils/` (PlantUML 1.2022.14, for the docs) — plus an
unpinned `releases/latest` download in the docker image, a fourth version that could change
without a commit.

- **The sdist.** Moving the jar *here* is what takes it out of the tarball, and that is true
  whether or not it is committed: `[tool.flit.sdist]` ships `tests/` and `docs/`, and flit's
  `include` patterns cannot escape the package directory, so a repository-root directory
  cannot enter the sdist at all. The two jars were 21,421,383 bytes on disk, and dropping
  them takes the 28,050,184-byte sphinx-needs sdist down by 19,962,751 bytes — **71 %**, to
  ≈8.1 MB against a 2.8 MB wheel. A distribution packager building from the sdist takes the
  `PLANTUML_JAR` or `plantuml`-on-`PATH` route below.
- **One version, said out loud.** It is in the filename and in `pin.toml`, and
  `uv run poe verify-plantuml` — which CI's Lint job and `uv run poe lint` both run — fails
  when the two disagree. The jar this replaces was called `plantuml.jar`, was PlantUML
  1.2022.5, and sat four years and ~46 releases behind without anyone noticing, because
  nothing in the tree said what it was.
- **Zero network.** A checkout renders. That is the whole point of committing it, and it is
  worth more than the ~30 MB: 22 jobs of a CI run render (measured: 24 jobs, all but `Lint`
  and the smoke test), Read the Docs builds on every pull request, developers work offline,
  and a sandboxed agent session's network allowlist is set
  on the environment rather than in this repository (this repository's own `CLAUDE.md` records
  `api.github.com` having to be added to it by hand).

  **A fetched design was built and reviewed on this same pull request first, and dropped.**
  In it `pin.toml` was committed and the jar was not: every consumer downloaded it on demand,
  from the release asset the pin names. Measured, that URL redirects to
  `release-assets.githubusercontent.com`, so every one of those four places would have had to
  be able to reach a host none of them is guaranteed to reach — for a file that never changes
  between bumps.
- **The cost, stated.** One ~30 MB blob enters the history at each bump, for ever. Before this
  change the repository already carried **six** jar blobs, 49,933,998 bytes, from the two it
  used to vendor; this one makes seven and 79,805,495 bytes. (Count them with
  `git rev-list --objects <ref>`, filtered to `.jar`, through `git cat-file --batch-check`.)
  That is accepted because bumps are rare — the jar this replaces was four years old — but it
  is not free, and two things bound it:
  **GitHub warns above 50 MB and refuses a file above 100 MB**, and PlantUML's jar has roughly
  tripled in four years (10,071,904 B at 1.2022.5, 29,871,497 B at 1.2026.8). If a future
  release crosses 50 MB, this bargain has to be re-made rather than repeated.

## The two other routes

Every consumer resolves a renderer in the same order:

1. **`PLANTUML_JAR`** — an absolute path to any plantuml jar, with `java` on `PATH`. An
   explicit choice wins, and a value that names no file is an error rather than a silent
   fall-through. This is the route for a distribution packager building from the sdist, and
   for anyone who already has a jar they would rather use.
2. **This directory**, at the pinned version — what a checkout of this repository gets.
3. **`plantuml`** (on Windows `plantumlc` first) **on `PATH`** — a system package, e.g.
   `apt install plantuml`, `brew install plantuml`, `choco install plantuml`.

Failing all three, the error names the routes that tree has: in a checkout,
`uv run poe fetch-plantuml` first; in an sdist, which ships neither this directory nor the
pin, `PLANTUML_JAR` and the executable.

## The step CI runs

Every workflow job that renders a diagram runs the same step, right after `setup-uv` and
before any `uv sync`:

```yaml
- name: Point PLANTUML_JAR at the vendored jar
  shell: bash
  run: |
    jar="$(uv run --no-project python tools/src/sn_tools/fetch_plantuml.py --verify | tr -d '\r')"
    echo "PLANTUML_JAR=$jar" >> "$GITHUB_ENV"
```

`--verify` checks the committed jar against the pin and never touches the network; the script
prints the jar's path on stdout and everything else on stderr, so the capture is the whole of
the plumbing. Each part of it is load-bearing:

- **`uv run --no-project`, after `setup-uv`.** The script needs `tomllib`, so Python 3.11+,
  and a runner's system python is not guaranteed to be one (the Windows image's default has
  been 3.9). uv supplies the interpreter the job asked for, and `--no-project` runs the
  script before anything is synced or resolved -- which is why it is stdlib-only.
- **`shell: bash`.** The Windows runners default to pwsh, and the bash GitHub gives a step
  without a `shell:` key is `bash -e`, under which a failing command inside `$( )` piped
  into `tr` exits 0 and the variable is silently empty. `shell: bash` selects
  `bash -eo pipefail`, so the pipeline carries the script's non-zero status and the step goes
  red. The assignment form matters for the same reason: `echo "PLANTUML_JAR=$(…)"` would
  exit 0 with an empty value and leave the failure to whatever reads the variable next.
- **`tr -d '\r'`.** On Windows python's `print()` writes CRLF and `$( )` strips trailing
  newlines only, so without it the variable carries a carriage return into `$GITHUB_ENV`.
- **A step writing `$GITHUB_ENV`, not a job-level `env:`.** Where the step is conditional
  (the reusable `test-package.yaml`, on its `needs-plantuml` input), an `env:` expression's
  failure mode is the literal string `false` -- drop the `|| ''` and actionlint is silent --
  while a skipped step leaves the variable genuinely unset, which is what both suites
  treat as "no explicit choice".

CI's **Lint** job runs the same `--verify` without the capture, beside the workspace-manifest
check. That is the fence on the pin: a pull request that edits `pin.toml` and does not commit
the matching jar is one red step naming both hashes, rather than a rendering failure in some
other job.

## Bumping the pin

1. Download the release asset and hash it:
   `curl -sSLO https://github.com/plantuml/plantuml/releases/download/v<version>/plantuml-<version>.jar`
   then `shasum -a 256 plantuml-<version>.jar` (`sha256sum` on Linux).
2. Edit `version` and `sha256` in `pin.toml` — both, always.
3. `uv run poe fetch-plantuml`, which downloads exactly what the new pin names and puts it
   here. Then `git rm vendor/plantuml/plantuml-<old>.jar` and
   `git add vendor/plantuml/plantuml-<new>.jar`.
4. Edit `ARG PLANTUML_VERSION` in `docker/Dockerfile` to the same value. (The image builds
   from a git ref with no checkout as its build context, so it downloads its own copy; this
   is the one place the version is repeated, and it is repeated deliberately.)
5. `uv run poe verify-plantuml` — the check Lint will make — and re-run the renderer-heavy
   suites: `uv run poe test-needs tests/test_plantuml.py tests/test_plantuml_incdir.py tests/test_needuml.py tests/test_needflow.py`,
   `uv run poe docs-needs`, `uv run poe test-mounts`.

**Pushing a bump may need `http.postBuffer`.** Over an HTTPS remote, git buffers a push body
up to `http.postBuffer` (1 MB by default) and switches to chunked transfer above it, which
GitHub answers with `error: RPC failed; HTTP 400`. It is not a size limit and not a refusal:
`git -c http.postBuffer=629145600 push …` sends the same objects and succeeds (measured
committing the 1.2026.8 jar).
