# Sphinx Mounts

Mount external source trees into a Sphinx build without copying or
symlinking. Sources stay where they live — for example, a Bazel `bazel-bin/`
output tree, a sibling repository, or a generated cache directory — and are
made visible to Sphinx at a configured docname prefix. RST works out of the
box; Markdown works as soon as `myst-parser` is loaded in the host project;
any other format a Sphinx parser extension registers is picked up the same
way.

## Features

- **No materialization**: sources are read directly from their original
  location. No copy, no symlink, no staging step.
- **Declarative TOML config**: the mount mapping lives in `ubproject.toml`
  (or any TOML file you name via `mounts_from_toml`). `conf.py` only
  references it.
- **Language-agnostic & toolable**: because the config is static TOML, IDE
  plugins, language servers, indexers, and build-system integrations
  written in any language can read the same mount mapping that
  `sphinx-build` reads — without having to evaluate `conf.py`.
- **Toctree auto-wiring**: an optional `attach_to` per mount injects the
  bundle's entry doc into a host toctree at build time, so the host stays
  buildable when a mount is absent (a developer hasn't run the upstream
  build, CI hasn't fetched the bundle).
- **Self-contained bundles**: each mount is intended to be a
  self-contained tree of `.rst` files with relative links only, so it can
  be reused across host projects. A linter is on the roadmap; the
  convention is not currently enforced.

## Quick Start

```bash
pip install sphinx-mounts
```

Add to your `conf.py`:

```python
extensions = ["sphinx_mounts"]
```

Describe your mounts in `ubproject.toml` next to `conf.py`:

```toml
[[mounts]]
dir = "/abs/path/to/bazel-bin/docs/api-foo"
mount_at = "_generated/api-foo"
```

Reference mounted documents from your host project just like any other doc:

```rst
.. toctree::

   _generated/api-foo/index
```

## Why TOML?

A `conf.py` is executable Python — only a Python interpreter can read it
correctly. A TOML file is static data, parseable by every common language.
Putting the mount mapping in `ubproject.toml` means that any external tool
(an IDE extension, a documentation indexer, a CI gate, a non-Python build
system) can resolve cross-references without running Sphinx. The same file
can also carry sections owned by sibling tools such as [Sphinx-Needs]
(`[needs]`) and [sphinx-codelinks] (`[codelinks]`), keeping the project's
documentation configuration in one place.

If TOML isn't an option for your setup, the legacy `mounts = [...]` list in
`conf.py` is still honored as a fallback — see the docs for details.

## Related projects

- [bazel-drives-sphinx] — a heavier take on Bazel-driven Sphinx
  documentation: Bazel rules declare every RST file (and `needs.json`
  artifact) as a label, and generated per-project targets invoke
  `sphinx-build` on the assembled tree. `sphinx-mounts` is the lightweight
  alternative — Bazel drops generated files under `bazel-bin/`, the
  extension mounts that directory, and Sphinx reads in place. Pick the
  former for fine-grained multi-project rule collection and tag-driven
  variants; pick the latter when "Bazel build, then Sphinx" is enough.
  See `docs/source/bazel.rst` for a side-by-side comparison.

## Documentation

See `docs/source/` for the full configuration reference and the Bazel
integration walkthrough. The "Related projects" section in
`docs/source/index.rst` lists sibling tools ([Sphinx-Needs],
[sphinx-codelinks], [ubCode], [bazel-drives-sphinx]) that share the
`ubproject.toml` convention.

## License

MIT — see [LICENSE](LICENSE).

[Sphinx-Needs]: https://sphinx-needs.readthedocs.io/
[sphinx-codelinks]: https://github.com/useblocks/sphinx-codelinks
[ubCode]: https://ubcode.useblocks.com/
[bazel-drives-sphinx]: https://github.com/useblocks/bazel-drives-sphinx
