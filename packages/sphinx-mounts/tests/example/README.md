# Full sphinx-mounts example (Bazel-driven)

This directory is a complete, checked-in reference example of a
sphinx-mounts setup whose external bundles are produced by Bazel.
Nothing here is bootstrapped at test time — every file you see is
the real file on disk. Browse the tree to see what the production
shape looks like.

The pytest binding at `../test_example.py` runs the whole pipeline
end-to-end (marked `bazel`, skipped when no `bazel`/`bazelisk` is on
`PATH`).

## Layout

    tests/example/
    ├── .bazelrc                       # bzlmod-only Bazel config
    ├── BUILD.bazel                    # :all_bundles, :build_docs, :docs_html
    ├── MODULE.bazel                   # depends on rules_shell
    ├── build_docs.sh                  # wrapper for ``bazel run //:build_docs``
    ├── build_docs_sandbox.sh          # wrapper for ``bazel build //:docs_html``
    ├── bundles/
    │   ├── api-foo/BUILD.bazel        # 2 RST files emitted by genrules
    │   └── api-bar/BUILD.bazel        # 1 Markdown file emitted by genrule
    └── docs/
        ├── conf.py                    # host Sphinx project (RST)
        ├── index.rst                  # host toctree — names api-bar only
        ├── installation.rst           # host-only page
        └── ubproject.toml             # two mounts, two wiring styles

## Pipeline

Run the commands below from this directory (`tests/example/`).

1. **Build the bundles with Bazel.**

   ```sh
   bazel build //:all_bundles
   ```

   Files appear under `bazel-bin/bundles/api-foo/` and
   `bazel-bin/bundles/api-bar/`. These are the paths
   `docs/ubproject.toml` mounts.

2. **Build the docs.** Pick one of the two Bazel entry points
   depending on whether you want the output in your source tree
   (iterative editing) or as a Bazel-tracked artefact (a release
   artifact, a CI handoff):

   ```sh
   # (a) In-workspace build — rendered HTML lands under
   #     ``docs/_build/html``. Convenient for live editing.
   bazel run //:build_docs

   # (b) Sandboxed build — rendered HTML lands under
   #     ``bazel-bin/docs_html.tar.gz`` as a Bazel-tracked artefact
   #     on the build graph. No source-tree mutation. This is what
   #     you wire into a downstream Bazel target (release packager,
   #     CI artifact upload, etc.).
   bazel build //:docs_html
   tar xzf bazel-bin/docs_html.tar.gz   # extract when you want to view
   ```

   Both targets live next to `:all_bundles` in `BUILD.bazel` and
   depend on it, so step 1 runs automatically if you skipped it.
   Both ultimately invoke `sphinx-build`; the difference is where
   the action runs and where its output lands.

   `sphinx-mounts` reads `docs/ubproject.toml`, mounts both Bazel
   bundles in place, and uses `attach_to = "index"` on the
   `api-foo` mount to wire its entry doc into the host's
   `index.rst` toctree at doctree-read time. The `api-bar` mount
   carries no `attach_to`, so the host's `index.rst` references its
   entry doc by hand. No `_generated/` directory is ever created in
   the source tree.

   Equivalent direct invocation if you prefer to skip Bazel for
   step 2:

   ```sh
   uv run sphinx-build -nW --keep-going -b html -c docs docs docs/_build/html
   ```

   *Note on the `:docs_html` genrule:* the action runs with `local
   = 1` and calls `uv` from `PATH`, because the umbrella project's
   Python deps (`sphinx`, `sphinx-mounts`, `myst-parser`) live in
   its uv-managed venv at `../../`. Projects that need a fully
   sandboxed, hermetic build can swap the wrapper for a
   `rules_python` `py_binary` with a pinned `requirements.txt`; the
   genrule shape stays the same.

3. **Edit with ubCode** *(future capability — not available
   today)*. Once the ubCode language server adds support for the
   `[[mounts]]` schema in `ubproject.toml`, opening any RST/MD file
   under `docs/` will resolve cross-references to the mounted
   bundles automatically — provided step 1 has already run so the
   bundle files exist on disk. This integration is on the roadmap;
   the TOML shape in this example is the same one ubCode will
   read.

## What to notice

- **Two wiring styles side-by-side.** `api-foo` (RST) uses
  `attach_to` + `entry_doc` and never gets mentioned in the host's
  source RST. `api-bar` (Markdown) is a "raw" mount with no
  `attach_to`; the host references its entry doc by hand in
  `docs/index.rst`. Both result in toctree links in the rendered
  `index.html`.
- **`ubproject.toml` paths are TOML-anchored.** `dir =
  "../bazel-bin/bundles/api-foo"` resolves relative to *this*
  TOML's directory (`docs/`), not to wherever Bazel happens to be
  invoked from. The Bazel `bazel-bin` / `bazel-out` symlinks sit at
  the workspace-relative path on every OS, so this TOML is
  check-in-able as-is.
- **Mixed formats.** `api-foo` is RST and `api-bar` is Markdown;
  both flow through the same mount with no per-format setup beyond
  loading `myst_parser` in the host's `conf.py`.
- **Bundle discipline.** Each bundle is a self-contained tree with
  relative `:doc:` / Markdown links only. Neither bundle references
  back into the host project — see
  [Integration → Anti-pattern: mounted sources linking back to the
  host](../../docs/source/integration.rst) for why.

## Running the test

From the repo root:

```sh
tox -e bazel                                # full bazel job
# or, with deps already in the current environment:
uv run pytest -m bazel tests/test_example.py
```

The test copies this directory into a temporary workspace (so your
real `bazel-bin/` is not touched), runs `bazel build //:all_bundles`
with an isolated `--output_base`, runs `sphinx-build` against the
host project, and asserts that the rendered HTML contains content
from the host, the RST bundle, and the Markdown bundle — and that
both wiring styles (`api-foo` via `attach_to`, `api-bar` via the
host's hand-written toctree entry) produce links in the host's
`index.html`.
