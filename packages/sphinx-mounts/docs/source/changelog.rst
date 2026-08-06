.. _changelog:

Changelog
=========

.. _`release:0.1.3`:

0.1.3
-----

:Released: 2026-08-06

- Mounted paths are now registered with the same type the running Sphinx uses
  for its own documents — ``str`` on Sphinx 7.4, ``pathlib.Path`` from Sphinx
  8.0 on. Sphinx changed the type it keeps in ``Project._docname_to_path`` /
  ``_path_to_docname`` in 8.0, and each version reads those maps back assuming
  its own type, so no single stored type is correct across the supported
  range. Storing ``Path`` unconditionally crashed every HTML build with a
  mount on Sphinx 7.4 (``TypeError: 'PosixPath' object is not subscriptable``,
  raised while writing output); storing ``str`` unconditionally would instead
  make ``env.path2doc()`` silently return the absolute path minus its suffix
  rather than the docname on Sphinx 8.0+, which surfaces as spurious
  "document isn't included in any toctree" warnings for mounted documents
  pulled in via ``include::``. See `issue #21
  <https://github.com/useblocks/sphinx-mounts/issues/21>`__.

- Documented how `Sphinx-Needs <https://sphinx-needs.readthedocs.io/>`__
  directives resolve file paths inside a mounted bundle, and which of those
  references ``path_check`` and Sphinx's incremental rebuild can see — see
  :ref:`needs-file-references`. No behaviour change in the extension itself.

  The example project gained a ``showcase/needs`` bundle covering all three
  doc-relative references (``needimport``, ``needreport`` ``:template:``, and
  the PlantUML ``!include`` shared by ``needuml`` / ``needarch``), one page per
  directive, plus matching non-Bazel tests in
  ``tests/test_path_directives.py``. The example's host project also reads its
  Sphinx-Needs options from the ``[needs]`` table of the same
  ``ubproject.toml`` that declares the mounts, demonstrating the shared-TOML
  convention end to end.

.. _`release:0.1.2`:

0.1.2
-----

:Released: 2026-07-29

- New per-mount ``attach_each`` option (file-list mode only). With
  ``attach_to`` set, ``attach_each = true`` wires *every* listed file into
  the host toctree — in ``files`` order — instead of only ``entry_doc``, so
  a hand-picked set of loose files can be mounted without authoring an
  ``index`` doc to stitch them together (and without the orphan warnings
  that would otherwise fail a ``-W`` build). Requires ``attach_to``, is
  mutually exclusive with ``entry_doc``, and is rejected in directory mode;
  all three are enforced at config validation. See :ref:`attach-each`.

.. _`release:0.1.1`:

0.1.1
-----

:Released: 2026-06-14

- Added per-mount ``path_check`` option (``"error"`` default / ``"warn"`` /
  ``"off"``). Directives inside a mounted bundle that reference a file
  outside the bundle root (a leading-slash path, or one that climbs out
  with ``..``) now fail the build by default, keeping bundles
  self-contained. Set ``path_check = "warn"`` or ``"off"`` to relax it.
- Documented and added regression tests confirming that build diagnostics
  (warnings and errors) for mounted documents are emitted with the
  **absolute** path of the external source file plus a line number — so an
  editor's problem matcher, a terminal Ctrl+click, or a CI annotation can
  jump straight to the real source. Covered across docutils-native directives,
  Sphinx core, and third-party extensions (``sphinxcontrib.plantuml`` /
  ``sphinxcontrib.mermaid``). See :ref:`diagnostic-locations`.
- Added regression tests confirming Sphinx's incremental rebuild re-reads
  mounted documents when their content changes. Two paths are covered: a
  file-list-mounted doc whose own source is edited, and a mounted doc whose
  *referenced* file changes while the doc itself is untouched — the latter
  across every file-referencing directive (``literalinclude``, ``include``,
  ``csv-table :file:``, ``raw :file:``, ``image``, ``figure``, ``graphviz``,
  ``uml``, ``mermaid``). Detection needs no extension code: it rides on the
  absolute external paths recorded in ``Project._docname_to_path`` and
  ``env.dependencies``, which Sphinx stats on each rebuild.
- The CI test matrix now exercises Sphinx 8 on Python 3.12, alongside the
  existing Sphinx 7 and Sphinx 9 cells. The matrix previously covered only
  the lower (``>=7.4``) and upper (``<10``) bounds of the supported Sphinx
  range, leaving Sphinx 8 in the middle untested; all three major versions
  are now verified on every CI run.

.. _`release:0.1.0`:

0.1.0
-----

:Released: 2026-05-21

Initial release of **sphinx-mounts** — a Sphinx extension that mounts external
RST source trees into a Sphinx build *without copying or symlinking the
files*. Sources stay where they live (a Bazel ``bazel-bin/`` output tree, a
sibling repository, a generated cache directory) and are made visible to
Sphinx at a configured docname prefix.

Mount-aware project
...................

- Mount-aware :class:`sphinx.project.Project` subclass that injects external
  docnames at ``builder-inited`` time. Sphinx's reader opens the absolute
  external path directly: storing absolute paths in
  ``Project._docname_to_path`` means that when Sphinx later computes
  ``srcdir / stored_path`` the absolute right operand wins and the external
  file is read in place.
- Discovery iterates whatever Sphinx has registered in
  :confval:`sphinx:source_suffix`, so any format with a parser extension
  is supported: ``.rst`` by default, ``.md`` when ``myst_parser`` is
  loaded, plus anything else a project plugs in. See
  :ref:`source-formats`.
- Two mount modes, mutually exclusive per mount: **directory mode**
  (``dir = "..."`` walks a tree) and **file-list mode**
  (``files = [...]`` cherry-picks individual files, possibly just one).
  File-list basenames become flat docname tails under ``mount_at``;
  every listed file must have an extension Sphinx knows about.
- ``mount_at`` is now optional. When omitted, the bundle mounts at the
  host project root — a bundle file ``tutorial.rst`` becomes docname
  ``tutorial``. Useful when you want to pull a whole directory in as
  a source bundle with no prefix renaming.
- New per-mount ``strict_mount_at`` boolean (default ``false``) makes
  a host directory at ``<srcdir>/<mount_at>/`` a build error before
  file discovery. The default per-docname collision check stays the
  only gate when ``strict_mount_at`` is left off; the new flag is for
  tightly-disciplined projects that want any host directory at the
  mount point to fail loudly rather than pass silently. Rejected at
  config validation when combined with a root mount, since the host
  srcdir always exists. See :ref:`strict-mount-at`.
- Relative paths declared in ``ubproject.toml`` are anchored to the
  **TOML file's own directory** (not to ``confdir``). The TOML is
  therefore self-describing — placing it in a subdirectory of confdir
  no longer silently re-anchors its paths. ``conf.py``-declared mounts
  still anchor to ``confdir`` as before. See :ref:`path-anchoring`.
- Directory mounts are now walked with `ignore-python
  <https://pypi.org/project/ignore-python/>`__ — the same Rust ``ignore``
  crate binding that drives `sphinx-codelinks`_ and `ubCode`_. In-bundle
  ``.gitignore`` and ``.ignore`` files are respected by default; parent
  directories are *not* scanned (so mounts under a host-gitignored
  path such as ``bazel-bin/`` still discover their files). See
  :ref:`file-discovery`.
- Per-mount ``include`` / ``exclude`` lists replace the earlier
  ``exclude_patterns`` field, aligning with sphinx-codelinks'
  ``source_discover`` schema (``include`` allowlist, ``exclude``
  denylist, both gitignore-style). A new per-mount ``gitignore``
  boolean (default ``true``) lets a project opt out of honouring a
  sibling repository's ``.gitignore`` when mounting it.
- Bazel integration test fixture and ``tox -e bazel`` environment.

Declarative TOML config
.......................

- New ``mounts_from_toml`` config value (default ``"ubproject.toml"``) names
  a TOML file relative to ``confdir``. The TOML file is the **primary**
  config target, so IDE plugins, language servers, and other non-Python
  tooling can read the mount mapping without evaluating ``conf.py``. Schema
  is a top-level ``[[mounts]]`` array of tables. See :doc:`configuration`
  for the rationale.
- ``mounts = [...]`` in ``conf.py`` continues to work as a fallback when no
  TOML file is present, or when ``mounts_from_toml`` is set to ``None``. If
  both are present, the TOML file wins.

Toctree integration
...................

- New ``attach_to`` per-mount option auto-wires the mount's entry doc into a
  host toctree at build time, so the host doc can stay buildable when the
  mount is absent. ``toctree_index`` (0-based) picks *which* toctree in the
  host doc to extend; an out-of-range index fails the build loudly with an
  ``ExtensionError``. ``entry_doc`` (default ``"index"``) selects which file
  inside the mount is wired in.
- If ``attach_to`` is set and the host doc contains no toctree, the
  extension adds one **at the end of the first top-level section**. The
  host keeps full control of its content prefix; injected references are
  always at the bottom. See :ref:`toctree-integration`.
