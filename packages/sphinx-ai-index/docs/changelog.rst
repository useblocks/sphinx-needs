.. _changelog:

Changelog
=========

Unreleased
----------

Nothing about what the extension writes changes: ``ai_docs_index.json`` is the same file,
field for field, as 0.1.0 writes it.

- 🔧 Sphinx-AI-Index now lives in the Sphinx-Needs repository, as
  `packages/sphinx-ai-index <https://github.com/useblocks/sphinx-needs/tree/master/packages/sphinx-ai-index>`__.

  The whole of ``useblocks/sphinx-ai-index``' history came with it, rewritten so that
  every historical commit already places its files under that directory: ``git log`` and
  ``git blame`` read the full history there with no ``--follow``, and
  ``packages/sphinx-ai-index/design/import-commit-map.txt`` maps every hash the old
  repository had to its hash in the new one.

  - **The repository** is now https://github.com/useblocks/sphinx-needs. Pull requests and
    branches are opened there, under ``packages/sphinx-ai-index/``.
  - **Issues** move with it. New ones carry the ``pkg: sphinx-ai-index`` label, which the
    issue forms' "Package" dropdown sets.
  - **Release tags** are prefixed: ``sphinx-ai-index-v0.1.0`` rather than ``v0.1.0``, the
    one shape every package in that repository shares.
  - **The distribution keeps its name**, ``sphinx-ai-index``, and its import name,
    ``sphinx_ai_index``.

- ⬆️ **Python 3.11 or newer, and Sphinx 7.4 up to 9, are now required** (previously
  Python 3.9 and Sphinx 5.0, with no upper bound). That is the range the Sphinx-Needs
  repository tests every extension against -- Sphinx 7.4, 8.2 and 9.1 -- and the old
  tox cells for Python 3.9 and 3.10 and for Sphinx 5 and 6 went with the move, so the
  floor now states what is actually run. **docutils 0.21 or newer** is declared as well:
  the extension imports docutils directly, and 0.21 is the floor the repository
  type-checks against. The docutils requirement has no upper bound: Sphinx caps docutils
  per series itself.
- ✨ ``sphinx_ai_index.__version__`` is the package version, and ``setup()`` reports it to
  Sphinx as the extension's version rather than a second hand-written copy.

.. _`release:0.1.0`:

0.1.0
-----

:Released: 2026-03-16

- Initial release
