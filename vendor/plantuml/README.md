# `vendor/plantuml/`

The workspace's PlantUML renderer: **one** jar, at **one** pinned version, for every package
in this repository. `pin.toml` names it; `uv run poe fetch-plantuml` downloads it here as
`plantuml-<version>.jar`, which `.gitignore` keeps out of git.

Everything that renders a diagram in this repository reads this one pin — sphinx-needs' test
suite (`tests/conftest.py`) and its documentation (`docs/conf.py`), the performance project,
the sphinx-mounts suite (through `PLANTUML_JAR`, which CI and the poe tasks set from here),
`ci.yaml`, `release.yaml`, `benchmark.yaml`, `docs.yaml` and Read the Docs. The docker image
is the one exception it cannot be: a `Dockerfile` cannot read TOML, so `docker/Dockerfile`
repeats the version in an `ARG` and says so.

## Why the jar is fetched rather than committed

Until this directory existed the repository carried **two** jars at **two** versions —
one under `packages/sphinx-needs/tests/doc_test/utils/` (PlantUML 1.2022.5, for the tests)
and one under `packages/sphinx-needs/docs/utils/` (PlantUML 1.2022.14, for the docs) — plus an
unpinned `releases/latest` download in the docker image, a fourth version that could change
without a commit.

- **The sdist.** The two jars were 21,421,383 bytes on disk, and dropping them takes the
  28,050,184-byte sphinx-needs sdist down by 19,962,751 bytes — **71 %** — because `[tool.flit.sdist]` ships `tests/` and `docs/`. PyPI's 8.5.0 sdist is
  28.2 MB against a 2.8 MB wheel. A repository-level directory cannot be included by flit at
  all (its `include` patterns cannot escape the package directory), so moving the jar here is
  what removes it from the tarball.
- **git history.** Six distinct jar blobs, 49.9 MB, are already in this repository's history,
  and every clone pays for them for ever. Nothing can reclaim that — but a fetched jar stops
  it growing at the next bump.
- **Age.** The test jar was four years and ~46 releases old, and nothing said so: its filename
  carried no version. A pin file that is one line to read and two lines to edit does.

The cost is that a fresh clone no longer renders diagrams with nothing installed. That is the
same bargain `poe install-browser` already makes for the playwright browser tests, and the
tasks that need a jar declare `deps = ["fetch-plantuml"]`, so `uv run poe test-needs` still
does the right thing on its own.

## The two routes that need no download

Every consumer resolves a renderer in the same order:

1. **`PLANTUML_JAR`** — an absolute path to any plantuml jar, with `java` on `PATH`. An
   explicit choice wins, and a value that names no file is an error rather than a silent
   fall-through. This is the route for an offline machine, a distribution packager building
   from the sdist, and anyone who already has a jar.
2. **This directory**, at the pinned version.
3. **`plantuml`** (on Windows `plantumlc` first) **on `PATH`** — a system package, e.g.
   `apt install plantuml`, `brew install plantuml`, `choco install plantuml`.

Failing all three, the error names `uv run poe fetch-plantuml` and the two alternatives.

## The step CI runs

Every workflow job that renders a diagram runs the same step, right after `setup-uv` and
before any `uv sync`:

```yaml
- name: Fetch the pinned PlantUML
  shell: bash
  run: |
    jar="$(uv run --no-project python tools/src/sn_tools/fetch_plantuml.py | tr -d '\r')"
    echo "PLANTUML_JAR=$jar" >> "$GITHUB_ENV"
```

The script prints the jar's path on stdout and everything else on stderr, so the capture is
the whole of the plumbing. Each part of it is load-bearing:

- **`uv run --no-project`, after `setup-uv`.** The script needs `tomllib`, so Python 3.11+,
  and a runner's system python is not guaranteed to be one (the Windows image's default has
  been 3.9). uv supplies the interpreter the job asked for, and `--no-project` runs the
  script before anything is synced or resolved -- which is why it is stdlib-only.
- **`shell: bash`.** The Windows runners default to pwsh, and the bash GitHub gives a step
  without a `shell:` key is `bash -e`, under which a failing command inside `$( )` piped
  into `tr` exits 0 and the variable is silently empty. `shell: bash` selects
  `bash -eo pipefail`, so the pipeline carries the fetch's non-zero status and the step goes
  red. The assignment form matters for the same reason: `echo "PLANTUML_JAR=$(…)"` would
  exit 0 with an empty value and leave the failure to whatever reads the variable next.
- **`tr -d '\r'`.** On Windows python's `print()` writes CRLF and `$( )` strips trailing
  newlines only, so without it the variable carries a carriage return into `$GITHUB_ENV`.
- **A step writing `$GITHUB_ENV`, not a job-level `env:`.** Where the step is conditional
  (the reusable `test-package.yaml`, on its `needs-plantuml` input), an `env:` expression's
  failure mode is the literal string `false` -- drop the `|| ''` and actionlint is silent --
  while a skipped step leaves the variable genuinely unset, which is what both suites
  treat as "no explicit choice".

A jar that failed to arrive is therefore a red step named after the fetch, not a quieter
test run: the suites that read the variable assert on a renderer rather than skip.

## Bumping the pin

1. Download the release asset and hash it:
   `curl -sSLO https://github.com/plantuml/plantuml/releases/download/v<version>/plantuml-<version>.jar`
   then `shasum -a 256 plantuml-<version>.jar` (`sha256sum` on Linux).
2. Edit `version` and `sha256` in `pin.toml` — both, always.
3. Edit `ARG PLANTUML_VERSION` in `docker/Dockerfile` to the same value.
4. `uv run poe fetch-plantuml` and re-run the renderer-heavy suites:
   `uv run poe test-needs tests/test_plantuml.py tests/test_plantuml_incdir.py tests/test_needuml.py tests/test_needflow.py`,
   `uv run poe docs-needs`, `uv run poe test-mounts`.
