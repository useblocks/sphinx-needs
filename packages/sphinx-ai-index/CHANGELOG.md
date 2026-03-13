# Changelog

## 0.1.0 (unreleased)

- Initial release, extracted from the ubcode monorepo.
- Fixed global mutable state: replaced module-level dict with a
  `WeakKeyDictionary` keyed on the `Sphinx` app instance, preventing state
  leakage between builds running in the same Python process (e.g.
  sphinx-autobuild, test suites).
- Fixed `app.outdir` usage to be compatible with Sphinx < 7.2 by wrapping
  with `pathlib.Path`.
- Simplified guard condition in `on_doctree_resolved` to a plain
  `if app.builder.name != "html": return`.
- Set `parallel_read_safe = True` (the extension only hooks write-phase
  events; read-phase parallelism is unaffected).
