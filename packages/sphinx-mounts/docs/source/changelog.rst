.. _changelog:

Changelog
=========

Unreleased
----------

.. note::

   **Cache invalidation:** the extension now declares an ``env_version``, so
   the first build after upgrading discards its cached build environment and
   re-reads every document once. No action is required.

.. warning::

   **Deprecation:** declaring the mounts array as top-level ``[[mounts]]`` now
   emits a ``mounts.deprecated_location`` warning. Use ``[[source.mounts]]``
   instead — migrating is a rename of the table header and nothing else:

   .. code-block:: diff

      -[[mounts]]
      +[[source.mounts]]
       dir = "../shared-bundles/api-bar"

   The old spelling still loads, with identical keys, anchoring and
   validation; only the diagnostic is new. It matters because other tools read
   this same file and recognise only ``[[source.mounts]]``, and two readers
   disagreeing about which tables count means one file describing two
   different projects.

   Note this **will fail a** ``sphinx-build -W`` **build** until you migrate.
   If you cannot yet, suppress just this one and keep ``-W`` for everything
   else::

      suppress_warnings = ["mounts.deprecated_location"]

   Removal of the top-level spelling is not scheduled in this release.

.. warning::

   **Behavior change:** ``path_check`` now defaults to ``"warn"`` instead of
   ``"error"``. A reference that escapes a mount's bundle root is reported as a
   ``mounts.path_escape`` warning and the build continues, where it previously
   aborted the build.

   To keep hard failures, do either of:

   - build with ``sphinx-build -W`` (recommended for CI — it escalates *every*
     mount warning, not just this one); or
   - set ``path_check = "error"`` explicitly on the mounts that want it. That
     mode is otherwise unchanged.

   Rationale: every other mount-specific problem in this extension is a typed,
   suppressible warning that ``-W`` escalates, and
   ``sphinx_mounts.logging`` states that as the doctrine — an escaping
   reference is no different. The hard default also promised more than its
   placement can deliver: the check runs from ``env-check-consistency``, which
   Sphinx skips entirely on a build that reads no document, so it was never a
   standing invariant.

- ``attach_to`` wiring now tracks bundles appearing and disappearing across
  **incremental** builds, in both directions and without ``sphinx-build -E``.
  Previously the wiring went stale and never recovered: a bundle whose entry
  doc was removed left a dead link in the output plus a repeating "toctree
  contains reference to non-existing document" warning on every later build
  (a failure under ``-W``), and a bundle whose entry doc appeared was
  rendered but silently missing from the navigation. Only a full rebuild
  cleared either state, which contradicted the documented promise that a host
  project stays buildable as its mounts come and go. Only documents named by
  an ``attach_to`` are re-read, and only when that mount's contribution
  actually changed. See :ref:`incremental-rebuilds`.

- Two files of the **same** mount that map to one docname are now reported as
  a ``mounts.docname_conflict`` instead of silently overwriting each other.
  This affected both modes — two listed files sharing a basename (file-list
  mode is a flat namespace), and two files differing only in registered
  suffix such as ``index.rst`` beside ``index.md`` — and in both cases a
  document disappeared from the build with no diagnostic at all, where core
  Sphinx reports "multiple files found for the document" for the same
  situation in the host source directory. The warning names both contributing
  paths.

- Every ``docname conflict`` message now states how many files the whole-mount
  skip drops, and which knob resolves it. One colliding filename removing a
  whole bundle is a large consequence to report in a single line of a long
  build log. The remedy is mode-dependent: a file-list mount is told to drop
  an entry from ``files``, since ``include`` / ``exclude`` would have no
  effect there.

- ``include`` or ``exclude`` on a **file-list** mount is now reported as
  ``mounts.ignored_option``. Those keys are patterns for the directory
  walker, and a file-list mount has none, so they were silently doing
  nothing — the only contradictory key combination in the extension that was
  neither rejected nor reported.

- A file-list mount's ``path_check`` **roots are now the union of its listed
  files' directories**, so a reference is in-bundle when it sits under any
  directory the mount named. Each document was previously confined to its own
  file's parent, which made the verdict depend on how deep a file sat in the
  tree — a reference from ``index.rst`` down into ``notes/`` passed, while the
  mirror-image reference from ``notes/2026-q1.rst`` up to a shared
  ``../shared.txt`` was rejected as leaving "the bundle root", in the same
  mount and the same tree. The union fixes that without ever admitting a
  directory that was not named: notably it is *not* the common ancestor of the
  listed files, which the ``files`` list could drive arbitrarily wide — up to
  the filesystem root for entries on unrelated branches, silently permitting
  every file on the machine.

.. note::

   **For projects that suppressed** ``mounts.path_escape``: the false positive
   described above (a reference between two files of the same file-list mount)
   used to be reported with the *same* subtype as a genuine escape, so
   silencing one silenced both. With the false positive gone, a project that
   suppressed the subtype to quiet it will start seeing the genuine escapes it
   was hiding. That is the intended outcome; review the suppression.

- The ``path_check`` containment comparison now applies the platform's path
  case normalisation, which folds on **Windows only** — on POSIX, macOS
  included, it is the identity function. Resolving a path does not fold case,
  so on Windows a bundle configured as ``C:/x/Bundle`` whose real directory is
  ``bundle`` could have a perfectly legitimate in-bundle reference rejected as
  an escape. On macOS the comparison stays case-sensitive even though the
  default filesystem is not, so a reference's written case must match the
  bundle root's own spelling there.

- A ``path_check = "error"`` failure is now attributed to this extension —
  the report reads ``Extension error (sphinx_mounts)`` instead of a bare
  ``Extension error`` — and the human-readable message is logged before the
  build aborts, so the line explaining what to fix is not buried inside a
  crash report that invites the user to open an issue against Sphinx.

- The ``mounts.path_escape`` message now prints the recorded dependency
  alongside its resolved form, names the mount that owns the bundle root, and
  states that a symlink pointing out of the bundle is an escape too. The old
  advice — avoid a leading ``/`` and ``..`` climbing — described nothing the
  author had written when the escape ran through a symlink.

- A listed file whose whole name is a source suffix (a file called ``.rst``)
  is now rejected with ``mounts.empty_docname`` and the usual whole-mount
  skip. It previously produced a docname that was just the mount prefix with
  a trailing slash — or, for a root mount, the empty string, which wrote a
  dotfile page at the very root of the site — with no diagnostic.

- ``mount_at``, ``attach_to`` and ``entry_doc`` now **reject** an interior
  empty segment (``a//b``), a ``.`` segment (``a/./b``, or a bare ``.``), and
  leading or trailing whitespace, as configuration errors. All were previously
  accepted verbatim, because only surrounding slashes were trimmed. A docname
  is matched literally rather than resolved as a filesystem path, so each
  produced something no host document can match, and the mount was accepted
  and then silently unreferenceable.

  A bare ``mount_at = "."`` was worse than unreferenceable: written to mean
  "the project root", it produced the docname ``./index`` alongside the host
  project's own ``index``, so two distinct docnames resolved to one output
  file and the mounted page was overwritten with no diagnostic at all. Omit
  ``mount_at`` for a root mount.

- Trailing slashes are now **also** normalised away on ``entry_doc``
  (``index/`` is ``index``), as they always were on ``mount_at`` and
  ``attach_to``. Previously ``entry_doc = "index/"`` mounted the bundle and
  then never wired it into the host toctree, reported only as a
  ``toc.not_included`` against the bundle's own file — nowhere near the
  setting responsible.

- ✨ The mounts array is now declared as ``[[source.mounts]]``, and the
  top-level ``[[mounts]]`` spelling is **deprecated**. ``[source]`` is the
  table that owns source discovery in the shared ``ubproject.toml``
  vocabulary. Declaring both in one file remains a hard configuration error
  naming both locations. See :ref:`where-mounts-live`.

- The extension no longer serialises its own configuration objects into
  ``environment.pickle``. The parsed mount list, per-document bundle roots
  and per-mount docname lists are rebuilt on every build, so keeping them in
  the cache only added weight and pinned the private layout of internal
  classes. ``setup()`` also declares an ``env_version`` now, so a future
  change to what the extension stores in the environment invalidates stale
  caches instead of being restored into a shape their writer never produced.

- Documentation corrections, several of which contradicted the
  implementation:

  - An out-of-range ``toctree_index`` is a warning, not an
    ``ExtensionError``; the page previously said both.
  - The TOML-versus-``conf.py`` rule is that the TOML wins when it
    **declares mounts**, not merely when the file exists — so a
    ``ubproject.toml`` present for other tools leaves ``conf.py`` in charge,
    while an explicitly empty array is a deliberate override.
  - ``dir`` and ``files`` paths are always resolved, symlinks included, even
    when already absolute. Diagnostics therefore name the resolved location.
  - A multi-dot suffix strips the **first** match in ``source_suffix``
    registration order, not the longest; register longer suffixes first.
  - The ``include`` / ``exclude`` override list is last-match-wins, so a
    broad ``exclude`` beats a narrow ``include`` regardless of key order.
  - ``path_check`` detects rather than prevents, and is skipped entirely on a
    build that reads no document. Both are now stated outright.
  - The in-bundle asset-name collision hazard is documented next to
    ``path_check``: two bundles shipping ``diagram.png`` get one plain and
    one numbered ``_images`` name, decided by document read order.
  - ``attach_to`` may point at a **mounted** document, composing one mount
    into another. This worked but was undocumented.
  - ``integration.rst`` lists all seven event handlers (it claimed five and
    omitted the one behind ``path_check``), no longer claims that
    ``config-inited`` checks path existence, and its illustrative
    ``discover()`` snippet matches the real signature.
  - The renderer binaries ``dot`` and ``plantuml`` are documented as a test
    prerequisite; the ``pyproject.toml`` comment claiming otherwise was
    stale.

- ✨ New for implementers of a second reader: ``design/mapping-contract.md``
  is the normative specification of the mount mapping — per-key types and
  defaults, path anchoring and resolution, the pattern dialect (and how it
  differs from the same-named ``[source]`` keys owned by other tools),
  docname derivation, every collision tie-break, and the warning subtypes
  declared as a stable contract.

- ``design/mapping-contract.md`` also records, in a new §11, the divergences
  declared by ubCode as the contract's first second reader — what each tool
  does at every such point, and why the difference was chosen — so a project
  built by both can predict where they disagree. §9's case-folding note is
  corrected in the same change: the fold is Windows-only, so on macOS the
  containment comparison is case-sensitive even though the default filesystem
  is not.

.. _`release:0.1.4`:

0.1.4
-----

:Released: 2026-08-11

.. note::

   **Breaking behavior change:** problems that previously failed the build
   outright — a ``docname conflict``, a ``strict_mount_at`` violation, an
   out-of-range ``toctree_index``, a missing ``dir``/``files`` path, or a
   file with an unrecognised suffix — are now **warnings**. The affected
   **whole mount** is skipped — nothing of it is mounted, so the host
   project stays completely untouched (no partial mounts, no orphaned
   docs, no dangling toctree references) — and the build continues. To
   keep treating any of them as a hard failure, build with
   ``sphinx-build -W`` (warnings as errors).

- Expected configuration problems are now reported through Sphinx's
  warning/error machinery instead of as ``ValueError`` tracebacks (`issue
  #25 <https://github.com/useblocks/sphinx-mounts/issues/25>`__):

  - **Hard errors** (unreadable configuration — malformed TOML, wrong
    types, unknown keys) abort the build as an ``Extension error`` issued
    by :class:`sphinx.errors.ExtensionError` (attributed to this extension
    via its ``modname``). They are deliberately not suppressible:
    sphinx-mounts cannot proceed at all.
  - **Mount-specific problems** are warnings and each skips the **whole
    mount**: a ``docname conflict``, a missing ``dir``/``files`` path, a
    file with an unregistered suffix, and a ``strict_mount_at`` violation
    all drop the entire mount with exactly one warning — the build then
    emits *no* further warnings (no ``toc.not_included`` orphans, no
    ``toc.circular`` toctree noise), proving the host was left untouched.
    An out-of-range ``toctree_index`` skips only the toctree wiring and
    marks the mount's docs as orphans (no ``toc.not_included`` follows),
    and the existing ``attach_to``/``path_check`` warnings are typed too.
    Each
    warning names the offending mount by its config index and source path
    (e.g. ``mounts[0] (dir=/abs/path/to/bundle)``) and carries a
    ``mounts.<subtype>`` type, so users can suppress one problem
    (``"mounts.docname_conflict"``) or all of them at once
    (``"mounts"``) via
    :confval:`suppress_warnings <sphinx:suppress_warnings>` and escalate
    it to a build failure with ``sphinx-build -W``. See
    :ref:`warnings-and-errors`.

- The example project (``tests/example/docs``) gained a **warning
  showcase**: its ``ubproject.toml`` ends with one commented-out
  ``[[mounts]]`` block per warning the extension can emit, each with a
  comment explaining why it fires, backed by the demo bundles in
  ``tests/example/warnings/bundles/``. Uncomment a block and rebuild to
  see that warning in isolation; with all blocks commented the example
  builds warning-clean. See the "Warning showcase" section in
  ``tests/example/docs/ubproject.toml``.

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
