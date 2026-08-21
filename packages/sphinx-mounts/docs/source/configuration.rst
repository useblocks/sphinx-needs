Configuration
=============

sphinx-mounts is configured through a **declarative TOML file** that lives
alongside ``conf.py``. The TOML file is the primary, language-agnostic
config target; ``conf.py`` only points at it.

The default file name is ``ubproject.toml`` — a convention shared with
other useblocks tooling (`Sphinx-Needs`_, `sphinx-codelinks`_) so that
one declarative file can describe a documentation project's setup to
every downstream consumer. See :ref:`related-projects` for the full
list.

Why a TOML file (and not just ``conf.py``)?
-------------------------------------------

A Sphinx ``conf.py`` is executable Python — and a TOML-able mapping has
no business living inside it. Just to read the mapping out, a tool has
to install every extension ``conf.py`` imports, get ``sys.path`` right
so those imports resolve, spin up a Python interpreter, and evaluate
arbitrary code. That works for ``sphinx-build`` itself but is a heavy
lift for everything else: IDE plugins, language servers, linters,
indexers, build-system integrations, CI gates, and any tool written in
a language other than Python.

A TOML file is the opposite:

- **Static**: a parser reads keys and values; nothing is executed.
- **Universal**: TOML parsers exist in every common language (TypeScript,
  Rust, Go, Java, C#, ...). An editor plugin written in TypeScript can
  read the exact same mount mapping that ``sphinx-build`` reads, without
  shelling out to Python.
- **Composable**: the same ``ubproject.toml`` can carry sections owned by
  different tools (``[needs]`` for `Sphinx-Needs`_, ``[codelinks]`` for
  `sphinx-codelinks`_, ``[[source.mounts]]`` for sphinx-mounts, etc.). The
  project has one source of truth.
- **Diffable & reviewable**: a structured TOML diff is easier to review
  than a Python diff that may include expressions and side-effects.
- **Cacheable**: a content hash of the file is a stable cache key
  (mtime can serve as a fast proxy where the build system preserves
  it), so downstream tools can skip work when nothing has changed.
  ``conf.py`` evaluation depends on interpreter state, the surrounding
  environment, and which extensions are installed, so its result is
  not safely cacheable as a value — every consumer re-evaluates from
  scratch. In larger projects this dominates wall time on otherwise
  no-op rebuilds.

For a side-by-side comparison with the generic, driver-based
``sphinx-collections`` extension that solves a superset of the same
problem, see :ref:`vs-sphinx-collections` in the motivation page.

.. _writing-a-second-reader:

.. admonition:: Writing a second reader?
   :class: tip

   "Declarative TOML so any language can read the mapping" is only a real
   promise if the mapping is written down. `design/mapping-contract.md
   <https://github.com/useblocks/sphinx-mounts/blob/main/design/mapping-contract.md>`__
   in the repository is the normative specification: per-key types and
   defaults, path anchoring and resolution, the pattern dialect, docname
   derivation including suffix iteration order, every collision tie-break,
   and the warning subtypes declared as a stable contract. This page is
   the user-facing guide; that document is the one to implement against.

The conf.py-side configuration
------------------------------

Add the extension and (optionally) point at the TOML file:

.. code-block:: python

   # conf.py
   extensions = ["sphinx_mounts"]

   # Default — can be omitted.
   mounts_from_toml = "ubproject.toml"

``mounts_from_toml``
~~~~~~~~~~~~~~~~~~~~

Type: ``str | None``

Default: ``"ubproject.toml"``

Rebuild trigger: ``env``

Path (relative to ``confdir``) of the TOML file from which to load the
mount configuration. Set to ``None`` to disable TOML loading entirely;
the extension then falls back to a ``mounts = [...]`` value in
``conf.py`` (see :ref:`conf-py-fallback`).

.. _mount-semantics:

What "mount" means here
-----------------------

The name borrows from Linux ``mount(8)``, but the semantics differ in
ways worth being explicit about — assumptions carried over from the
operating-system meaning will lead you astray.

**``mount_at`` is a docname prefix, not a host filesystem path.** A
Linux mount target must already exist as a directory. In
sphinx-mounts, ``mount_at`` lives in Sphinx's *docname namespace*;
the host project does **not** need — and usually does not have — a
real directory at ``<srcdir>/<mount_at>/`` on disk. The mount adds
docnames of the form ``<mount_at>/<tail>``; whether or not a
directory exists at that path inside ``srcdir`` is irrelevant to
discovery.

**Mounting never shadows anything.** On Linux, mounting onto a
non-empty directory hides the original contents until you unmount.
In sphinx-mounts, a mount that would produce a docname already
provided by the host project (or by an earlier mount) is **skipped
entirely** with a ``docname conflict`` warning — the colliding file
*and* its siblings, so the host project stays completely untouched.
The same applies when two files of the *same* mount land on one
docname, which happens in both modes: two listed files sharing a
basename (file-list mode flattens the namespace), or two files
differing only in registered suffix such as ``index.rst`` beside
``index.md``. Nothing is silently hidden in either case; conflicts have
to be resolved by the author (rename one side, drop an entry from
``files``, narrow a directory mount's ``include`` / ``exclude``, or move
the host file). The warning names both contributing paths, how many files
the skip drops, and the remedy that applies to that mount's mode. See
:ref:`warnings-and-errors` for how to suppress or escalate it.

**There is no "unmount".** The mount mapping is read once per
``sphinx-build`` invocation and has no runtime lifecycle. Removing a
mount from ``ubproject.toml`` simply means the next build sees the
host project without those docnames; nothing is moved, copied, or
restored on disk.

**Sources are read in place.** No copy, no symlink, no staging step.
The "mount" is purely a view assembled inside Sphinx's docname
graph; the on-disk source tree is untouched. See
:ref:`vs-sphinx-collections` for the contrast with extensions that
materialize a staging tree.

The TOML schema
---------------

``ubproject.toml`` declares a ``[[source.mounts]]`` array of tables (see
:ref:`where-mounts-live`, and note that the old top-level ``[[mounts]]``
spelling is deprecated).
Each table is one mount entry, and is in one of two **mutually
exclusive** modes:

- **Directory mode** — the mount is a whole external tree. Use the
  ``dir`` key.
- **File-list mode** — the mount is a hand-picked set of individual
  files (possibly just one). Use the ``files`` key.

A single mount table must set ``dir`` *or* ``files``, never both
and never neither.

.. code-block:: toml

   # ubproject.toml

   # Directory mode: walk an entire tree.
   [[source.mounts]]
   dir = "/abs/path/to/bazel-bin/docs/api-foo"
   mount_at = "_generated/api-foo"

   [[source.mounts]]
   dir = "../shared-bundles/api-bar"
   mount_at = "_generated/api-bar"
   include = ["**/*.rst"]                # optional allowlist
   exclude = ["internal/**", "draft.rst"]
   gitignore = false                     # opt out of the bundle's .gitignore

   # File-list mode: cherry-pick individual files.
   [[source.mounts]]
   files = [
     "/abs/path/to/release-notes/2026-q1.md",
     "/abs/path/to/release-notes/2026-q2.md",
   ]
   mount_at = "_generated/release-notes"

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Key
     - Required
     - Description
   * - ``mount_at``
     - no
     - Docname prefix at which the mount appears. For example
       ``_generated/api-foo`` makes the file ``<dir>/index.rst``
       available as docname ``_generated/api-foo/index``. Must be
       relative (no leading slash, no ``..``). When omitted, the
       bundle mounts at the host project root — a bundle file
       ``tutorial.rst`` becomes docname ``tutorial``. See
       :ref:`root-mount` below.
   * - ``dir``
     - one of
     - **Directory mode.** Filesystem path to a directory containing
       source files. May be absolute, or relative to the
       :ref:`path anchor <path-anchoring>`. The directory must exist
       at build time. Any file extension registered with Sphinx via
       :confval:`sphinx:source_suffix` is discovered — ``.rst`` by
       default, ``.md`` when ``myst_parser`` is loaded, and anything
       else a parser extension registers. See :ref:`source-formats`
       below. Mutually exclusive with ``files``.
   * - ``files``
     - one of
     - **File-list mode.** Array of paths to individual source files.
       May be absolute, or relative to the
       :ref:`path anchor <path-anchoring>`. Each listed file should
       exist at build time and have an extension Sphinx knows about;
       a file that does not exist or has an unrecognised extension
       makes the **whole mount skipped** with a warning (the user
       explicitly asked for the files, so a silent skip would be wrong
       — see :ref:`warnings-and-errors`).
       Each file's *basename* (minus the matched suffix) becomes the
       docname tail under ``mount_at`` — subdirectories in the file
       paths are ignored, the result is a flat namespace. May contain
       a single file. Mutually exclusive with ``dir``.
   * - ``include``
     - no
     - Array of gitignore-style allowlist patterns evaluated relative
       to ``dir``. If non-empty, *only* files matching at least
       one pattern are discovered; everything else is filtered out.
       Defaults to ``[]``, which disables the allowlist entirely —
       every file the walker yields is offered to Sphinx, still
       subject to ``exclude``, the ``gitignore`` filter, and
       Sphinx's own ``source_suffix``. The user-visible set of
       mounted docs is therefore the same as
       ``include = ["**/*.*"]`` would produce (a registered source
       suffix always contains a dot), but ``[]`` is a no-op that
       skips the override step rather than an equivalent pattern.
       Only meaningful in directory mode. Aligns with
       sphinx-codelinks' ``source_discover.include``.
   * - ``exclude``
     - no
     - Array of gitignore-style exclusion patterns evaluated relative
       to ``dir``. Matching files are skipped after the ``include``
       allowlist runs. Defaults to ``[]``. Only meaningful in
       directory mode — in file-list mode the list itself is the
       filter. Aligns with sphinx-codelinks'
       ``source_discover.exclude``. See :ref:`file-discovery` below.
   * - ``gitignore``
     - no
     - Whether ``.gitignore`` and ``.ignore`` files *inside* the
       mounted tree filter the walk. Defaults to ``true``. Set to
       ``false`` to mount a sibling repository whose own
       ``.gitignore`` excludes content you nevertheless want to
       publish (release notes that have been gitignored away,
       generated trees served from a cache, etc.). Parent
       ``.gitignore`` files are never consulted regardless of this
       setting. Aligns with sphinx-codelinks'
       ``source_discover.gitignore``.
   * - ``attach_to``
     - no
     - Docname whose toctree should receive the mount entry — usually a
       host doc, but another mount's document works too (see
       :ref:`nested-mounts`). When set, the extension wires
       ``{mount_at}/{entry_doc}`` into that doc's toctree automatically.
       See :ref:`toctree-integration` below.
   * - ``toctree_index``
     - no
     - 0-based index selecting *which* toctree in ``attach_to`` to
       extend, in document order. Defaults to ``0`` (the first
       toctree). Ignored unless ``attach_to`` is set.
   * - ``entry_doc``
     - no
     - Mount-relative docname of the entry file to wire into the host
       toctree. Defaults to ``"index"``.
   * - ``attach_each``
     - no
     - File-list mode only. When ``true``, ``attach_to`` wires *every*
       listed file into the host toctree (in ``files`` order) instead of
       just ``entry_doc`` — so a set of loose files needs no index doc to
       stitch them together. Requires ``attach_to``, is mutually exclusive
       with ``entry_doc``, and is rejected in directory mode. Defaults to
       ``false``. See :ref:`attach-each` below.
   * - ``strict_mount_at``
     - no
     - Whether to fail the build if the host project has a directory
       at ``<srcdir>/<mount_at>/``. Defaults to ``false``. See
       :ref:`strict-mount-at` for the trade-off and when to enable it.
       Incompatible with a root mount (``mount_at`` omitted).
   * - ``path_check``
     - no
     - How to react when a directive inside a mounted doc references a
       file outside the bundle root. One of ``"warn"`` (default),
       ``"error"``, or ``"off"``. See :ref:`path-confinement` below.

.. _root-mount:

Mounting at the host project root
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Omitting ``mount_at`` mounts the bundle at the host's project root.
The common shape is pulling an entire directory of RST into the host
project as-is, with no prefix renaming:

.. code-block:: toml

   [[source.mounts]]
   dir = "./api"
   # mount_at omitted — files under ./api appear as bare docnames
   # (e.g. ./api/tutorial.rst → docname "tutorial").

The host project is responsible for ensuring no docname collides with
its own files. If a bundle file would shadow a host doc, sphinx-mounts
skips the **whole mount** and emits a ``docname conflict`` warning at
build time — see :ref:`warnings-and-errors`.

.. _strict-mount-at:

Strict mode: rejecting a pre-existing host directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Recall from :ref:`mount-semantics` that ``mount_at`` is a docname
prefix, not a host filesystem path — the host project typically has
no real directory at ``<srcdir>/<mount_at>/`` on disk, and that is
the expected case. A host directory accidentally sitting at the
mount point is usually a misconfiguration: either the mount is
aimed at the wrong prefix, or the host directory is stale and
forgotten.

The default per-docname collision check catches this *only* when
the host directory actually contains source files that would
shadow mounted ones; an empty host directory at ``mount_at``, or
one holding only non-source siblings (assets, ``.gitkeep``,
READMEs), passes silently. That permissiveness is sometimes useful
— a host may legitimately stage assets under a prefix it intends
to share with mounted content — but in tightly-disciplined
projects, the silent-pass case is the wrong default.

Set ``strict_mount_at = true`` on a mount to make any host
directory at ``<srcdir>/<mount_at>/`` skip the whole mount with a
``mount_at_occupied`` warning (see :ref:`warnings-and-errors`):

.. code-block:: toml

   [[source.mounts]]
   dir = "/path/to/bundle"
   mount_at = "_generated/api-foo"
   strict_mount_at = true

The check fires before any file discovery, with a message naming
the offending host path, and nothing of the mount is attached —
an occupied mount point means the bundle cannot be added without
modifying the host, so the only clean reaction is to skip it. Only
the leaf path is inspected; a host directory at a *parent* of
``mount_at`` (e.g. ``_generated/``) is fine — the mount slots a
virtual subdirectory under a real host section dir, which is a normal
pattern. The flag is mode-agnostic: file-list mounts honour it the
same way directory mounts do, since both share the ``mount_at``
docname prefix.

``strict_mount_at = true`` paired with a root mount (``mount_at``
omitted) is rejected at config validation — the host srcdir always
exists, so the check would have no meaningful failure mode and the
combination is almost certainly a configuration mistake.

.. _toctree-integration:

Toctree integration
-------------------

Without ``attach_to``, the host project is responsible for referencing
mounted documents itself — typically by listing them in a ``toctree``
directive. That works, but creates a chicken-and-egg problem: if the
mount is ever absent (a developer hasn't run the upstream build, a CI
job hasn't fetched the bundle), the static toctree entry becomes an
unresolved reference and the build fails.

``attach_to`` solves this by letting the extension wire the entry in *at
build time*, only when the mount is actually present:

.. code-block:: toml

   [[source.mounts]]
   dir = "/path/to/bazel-bin/docs/api-foo"
   mount_at = "_generated/api-foo"
   attach_to = "index"          # extend the toctree in index.rst

With this config, the host's ``index.rst`` can declare an empty (or
shorter) toctree:

.. code-block:: rst

   Host project
   ============

   .. toctree::
      :maxdepth: 2

The extension appends ``_generated/api-foo/index`` to that toctree
during the build. When the mount's entry doc is absent — the bundle was
never built, or its directory is empty — nothing is appended and the host
builds cleanly with whatever was already in the toctree.

That holds on **incremental** builds too, in both directions: a bundle
that appears is wired in on the very build it appears, and a bundle that
disappears is unwired on the build it disappears. Neither needs
``sphinx-build -E``. See :ref:`incremental-rebuilds` for the mechanism and
its one caveat.

.. _nested-mounts:

Attaching one mount into another
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``attach_to`` names a docname, and a *mounted* docname is a perfectly
good one. So a mount can be wired into another mount's toctree, which
lets an outer bundle act as the section index for a family of inner
bundles without the host project having to know about any of them:

.. code-block:: toml

   [[source.mounts]]
   dir = "../bundles/api"           # provides _generated/api/index
   mount_at = "_generated/api"
   attach_to = "index"              # ...wired into the HOST index

   [[source.mounts]]
   dir = "../bundles/api-foo"
   mount_at = "_generated/api/foo"
   attach_to = "_generated/api/index"   # ...wired into the OUTER MOUNT

Two things to keep in mind. Declaration order does not matter for
wiring — the injection happens while each document is read, not while
the config is parsed — but it *does* decide which mount wins a
:ref:`docname conflict <mount-semantics>`, since the first provider of a
docname keeps it.

.. warning::

   If the outer mount is skipped or absent — the normal state of a bundle
   whose upstream build has not run — the inner mount's ``attach_to`` target
   does not exist. The inner bundle is still mounted, just not referenced
   from anywhere, and that costs **N + 1 warnings**: one
   ``mounts.attach_to_missing``, plus one ``toc.not_included`` for *every*
   file of the inner bundle. Under ``sphinx-build -W`` a composed-mounts
   layout therefore fails whenever the outer bundle is missing.

   Unlike the out-of-range ``toctree_index`` case, the extension cannot
   collapse this to a single warning by marking the docs as orphans: Sphinx
   emits the ``toc.not_included`` warnings inside ``check_consistency()``
   *before* it fires the ``env-check-consistency`` event this extension
   listens on, so by the time the missing target is known the warnings have
   already been reported. (The ``toctree_index`` path can do it because it
   runs during the read phase.) Either add ``:orphan:`` to the inner
   bundle's files, or expect N + 1 warnings while the outer bundle is
   absent.

Picking a specific toctree
~~~~~~~~~~~~~~~~~~~~~~~~~~

A host doc may have several ``toctree`` directives — for example, a
top-level navigation toctree plus per-section sub-toctrees. Use
``toctree_index`` (0-based, document order) to pick the right one:

.. code-block:: toml

   [[source.mounts]]
   dir = "/path/to/api-foo"
   mount_at = "_generated/api-foo"
   attach_to = "index"
   toctree_index = 1            # extend the second toctree in index.rst

If ``toctree_index`` exceeds the number of toctrees actually present in
``attach_to``, a ``mounts.toctree_index`` warning is emitted and the mount
is left unwired — the host doc is never restructured to fit an index the
author did not write. Its documents are marked as orphans so the single
warning is not joined by one "not included in any toctree" per file. Use
``sphinx-build -W`` to make the misconfiguration fail the build; see
:ref:`warnings-and-errors`.

If ``attach_to`` is set but the doc contains **no** toctree at all, the
extension adds one at the **end** of the first top-level section and
populates it with the entry. Appending at the end (rather than the
start) keeps the host doc self-contained: any prose, directives, or
subsections the author wrote stay first, and the auto-injected mount
references are always placed below them. This makes a freshly
scaffolded host project work end-to-end without a hand-written
toctree, while still leaving the author in control of the page's
content prefix.

Choosing the mount-side entry file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The default entry is the mount's ``index.rst``. If the mount has a
different entry point (say ``overview.rst``), set ``entry_doc``:

.. code-block:: toml

   [[source.mounts]]
   dir = "../shared-bundles/api-bar"
   mount_at = "_generated/api-bar"
   attach_to = "index"
   entry_doc = "overview"

The resulting docname inserted into the toctree is then
``_generated/api-bar/overview``.

.. _attach-each:

Attaching every file: mounts without an entry doc
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``attach_to`` normally wires a single entry doc into the host toctree,
and that entry doc's own toctree is expected to reach the rest of the
bundle. That fits a directory bundle with a natural ``index``, but not
a hand-picked set of *loose* files with no index — those files would be
orphaned (Sphinx warns, and the build fails under ``-W``) unless you
author an ``index`` just to list them.

``attach_each`` removes that requirement. On a **file-list** mount it
makes ``attach_to`` append *every* listed file to the host toctree, in
``files`` order:

.. code-block:: toml

   [[source.mounts]]
   files = [
     "../fragments/note-one.rst",
     "../fragments/note-two.rst",
   ]
   mount_at = "_generated/fragments"
   attach_to = "index"
   attach_each = true

Both files become direct entries in ``attach_to``'s toctree
(``_generated/fragments/note-one`` and ``_generated/fragments/note-two``);
no index doc is needed and nothing is orphaned. Three constraints are
enforced at config validation:

- **File-list mode only.** A directory mount already has a natural entry
  doc (its ``index``) and would otherwise attach an unbounded, flat list
  of every walked file; ``attach_each`` on a ``dir`` mount is rejected.
- **Requires ``attach_to``.** Without a host toctree to attach into, the
  flag has nothing to do.
- **Mutually exclusive with ``entry_doc``.** ``attach_each`` attaches all
  files, so a single entry doc is meaningless; setting both is an error.

.. _where-mounts-live:

Where the mounts array lives: ``[[source.mounts]]``
---------------------------------------------------

Declare the array of tables under ``[source]``:

.. code-block:: toml

   # ubproject.toml
   [[source.mounts]]
   dir = "../shared-bundles/api-bar"
   mount_at = "_generated/api-bar"

``[source]`` is the table that owns source *discovery* in the
``ubproject.toml`` vocabulary shared with sibling tooling, which is what a
mount is, and namespacing keeps the file's root from growing into a flat
bag of keys.

.. deprecated:: next

   The original top-level ``[[mounts]]`` spelling still loads, identically
   — same keys, same :ref:`path anchoring <path-anchoring>`, same
   validation, same :ref:`conf.py fallback <conf-py-fallback>` semantics —
   but it now emits a ``mounts.deprecated_location`` warning. **Migrating
   is a rename of the table header and nothing else:**

   .. code-block:: diff

      -[[mounts]]
      +[[source.mounts]]
       dir = "../shared-bundles/api-bar"
       mount_at = "_generated/api-bar"

   The reason is not aesthetics. Other tools read this same file, and they
   honour only ``[[source.mounts]]``. Two readers disagreeing about which
   tables count is precisely the divergence the
   :ref:`mapping contract <writing-a-second-reader>` exists to prevent — an
   editor showing a page the build does not, or the reverse.

   If you cannot migrate yet, and especially if you build with ``-W`` (where
   any new warning is a hard failure), suppress just this one:

   .. code-block:: python

      # conf.py
      suppress_warnings = ["mounts.deprecated_location"]

   That leaves every other mount warning escalating as before. Removal of
   the top-level spelling is not scheduled here.

.. warning::

   Declaring **both** in one file is a hard configuration error naming
   both locations. Picking a winner (or merging the two) would make the
   effective mount list depend on a precedence rule that nobody reading
   the file can see.

.. note::

   ``[source]`` keys other than ``mounts`` are **not** read by
   sphinx-mounts, and a mount does not inherit anything from them. In
   particular ``[source].include`` / ``[source].exclude`` (owned by other
   tools) are a different pattern dialect from a mount's own
   ``include`` / ``exclude`` — see :ref:`file-discovery`. Nesting the
   array inside ``[source]`` is a naming decision, not an inheritance
   one.

.. _conf-py-fallback:

Fallback: ``mounts`` in ``conf.py``
-----------------------------------

If the TOML file is not present (or ``mounts_from_toml`` is set to
``None``), the extension reads the ``mounts`` value from ``conf.py``
instead. This is the legacy code path; it is retained for projects that
cannot adopt a TOML file yet.

.. code-block:: python

   # conf.py (legacy)
   mounts = [
       {
           "dir": "/abs/path/to/bazel-bin/docs/api-foo",
           "mount_at": "_generated/api-foo",
       },
       {
           "dir": "../shared-bundles/api-bar",
           "mount_at": "_generated/api-bar",
           "exclude": ("internal/**", "draft.rst"),
       },
   ]

The precise rule is that the TOML wins when it **declares mounts** — not
merely when the file exists:

- The TOML declares a mounts array (in either
  :ref:`location <where-mounts-live>`) → the TOML wins and ``conf.py``'s
  ``mounts`` is ignored.
- The TOML declares an **empty** array (``mounts = []``) → that is still a
  declaration, and a deliberate one: the project has no mounts, and
  ``conf.py``'s list is switched off.
- The TOML declares no mounts key at all → ``conf.py``'s ``mounts`` still
  applies. This is the common case for a ``ubproject.toml`` that exists
  only to configure *other* tools, and it means adding such a file to a
  project never silently disables its mounts.

.. _path-anchoring:

How relative paths in ``dir`` / ``files`` are resolved
------------------------------------------------------

Relative paths are anchored to the *file that declared the mount*,
never to the current working directory of the build:

- Mounts declared in ``ubproject.toml`` anchor to the **directory
  containing the TOML file**. So a path like ``../shared-bundles/x``
  inside ``docs/configs/mounts.toml`` resolves to
  ``docs/shared-bundles/x``, regardless of where ``conf.py`` lives or
  where ``sphinx-build`` is invoked from. Moving the TOML as a unit
  keeps its paths meaningful, and a TOML in a subdirectory of confdir
  does not silently re-anchor.
- Mounts declared in the legacy ``conf.py`` fallback anchor to
  ``confdir`` (the directory that holds ``conf.py``). This matches
  Sphinx's own conventions for ``conf.py``-relative paths.

Once anchored, **every** ``dir`` and ``files`` path is resolved: made
absolute, ``..`` segments collapsed, and symlinks followed. That applies to
paths that were already absolute too. Resolution is what makes
:ref:`path confinement <path-confinement>` correct for a bundle reached
through a symlink — the canonical Bazel case, where ``bazel-bin`` is a
symlink into the execroot — but it also means warnings and messages name
the resolved location rather than the path you wrote. A mount configured as
``bazel-bin/docs/api-foo`` is reported by its execroot path.

A path-resolution rule that surprises is worse than one that is verbose,
so prefer absolute paths (or the TOML-anchored form) when a project is
bundled across unusual directory layouts.

.. note::

   Because the resolved, absolute paths are what the extension hands to
   Sphinx as the ``mounts`` config value, **relocating or renaming the
   checkout changes that value and forces a full environment rebuild**,
   even when nothing about the project actually changed. That is the same
   mechanism that makes editing ``ubproject.toml`` correctly invalidate the
   cache, so it is a deliberate trade rather than an oversight. Editing
   only *comments* in the TOML changes nothing and correctly rebuilds
   nothing.

``mounts_from_toml`` itself is documented as a path relative to
``confdir``, and that is how it should be used. It does also accept an
absolute path, and a relative one may climb out of ``confdir`` with
``..``; neither is rejected. Keep in mind that the TOML's own directory
then becomes the anchor for the mount paths inside it, which is easy to
lose track of once the file lives outside the documentation tree.

.. _source-formats:

Source formats: RST, Markdown, and anything Sphinx knows about
--------------------------------------------------------------

sphinx-mounts does not parse files itself — it only attaches them to
the project. File discovery iterates whatever extensions Sphinx has
registered in :confval:`sphinx:source_suffix`. By default that's
``.rst``; loading additional parser extensions in the host project's
``conf.py`` is all that's needed to mount other formats:

.. code-block:: python

   # conf.py
   extensions = ["sphinx_mounts", "myst_parser"]

With ``myst_parser`` enabled, a mount may contain Markdown files:

.. code-block:: toml

   # ubproject.toml
   [[source.mounts]]
   dir = "../shared-bundles/release-notes"
   mount_at = "_generated/release-notes"

.. code-block:: text

   ../shared-bundles/release-notes/
   ├── index.md
   └── 2026-q2.md

Sphinx then reads those ``.md`` files in place — same docname
namespace, same ``attach_to`` wiring, same incremental rebuilds. The
same mechanism extends to any other parser-backed extension a project
chooses to add (e.g. ``rst2myst``, ``sphinxcontrib-jupyter``,
project-specific custom parsers).

.. _file-discovery:

File discovery
--------------

Directory mounts are walked with `ignore-python
<https://pypi.org/project/ignore-python/>`__, the Python binding for the
Rust ``ignore`` crate that also drives `sphinx-codelinks`_ and `ubCode`_.
A single, well-tested library means an editor preview and the build see
the same set of mounted docs — no glob-syntax drift between tools.

Walk policy used by sphinx-mounts:

- ``.gitignore`` and ``.ignore`` files *inside* the mounted tree are
  honoured when the per-mount ``gitignore`` flag is ``true`` (the
  default). Set ``gitignore = false`` on a mount whose source is a
  sibling repository whose own ``.gitignore`` excludes content you
  still want to publish — release notes that have been gitignored
  out of the repo, build artefacts mounted from a cache, etc. Note
  that ``.gitignore`` only takes effect when the mounted tree is
  itself a git repository (per the Rust crate's contract).
- Parent directories are **not** scanned for ignore files,
  regardless of the ``gitignore`` setting. This matters for the
  canonical Bazel layout — the workspace's root ``.gitignore``
  typically excludes ``bazel-bin/``, but a mount rooted at
  ``bazel-bin/docs/`` must still see every generated file.
- The user's global git config and ``.git/info/exclude`` are **not**
  consulted, so builds are reproducible across machines.
- Hidden entries (dotfiles, ``.git/``) are skipped. File-list mode has no
  walker, so it has no such rule — but a listed file whose whole name is a
  suffix (``.rst``) would have no docname at all, and is rejected with
  ``mounts.empty_docname``.
- ``include`` entries are added as positive gitignore-style overrides
  (allowlist): if non-empty, only files matching at least one
  pattern reach Sphinx. ``exclude`` entries are added as negated
  overrides (``!pattern``). Both lists are evaluated relative to
  ``dir``. Patterns like ``**/*.rst``, ``internal/**``, or
  ``draft.rst`` work as you would expect from a ``.gitignore`` file.

Both keys, and ``gitignore``, are read **only in directory mode**. A
file-list mount has no walker — the ``files`` list *is* the selection — so
setting ``include`` or ``exclude`` on one has no effect at all, and is
reported as ``mounts.ignored_option``. To filter a tree, use ``dir``.

The override list is **last-match-wins**, which is the one place the
gitignore intuition misleads: a broad ``exclude`` beats a narrow
``include`` regardless of the order the keys appear in the TOML, because
all ``include`` patterns are added before any ``exclude`` pattern. So

.. code-block:: toml

   [[source.mounts]]
   dir = "../bundle"
   mount_at = "_g/b"
   include = ["keep.rst"]
   exclude = ["**/*.rst"]

mounts **nothing**. To keep one file out of a broad exclude, narrow the
exclude rather than trying to out-specify it with an include.

.. _docname-derivation:

How a docname is derived
~~~~~~~~~~~~~~~~~~~~~~~~

A file's docname is ``mount_at`` plus a *tail*, and the tail is the file's
path with one matched source suffix removed:

- **Directory mode**: the tail is the file's path relative to ``dir``, so
  the bundle's directory structure is preserved.
- **File-list mode**: the tail is the file's *basename*. Subdirectories in
  the listed paths are dropped, giving a flat namespace under
  ``mount_at`` — which is why two listed files with the same basename
  collide.

The suffix removed is the **first** entry of
:confval:`sphinx:source_suffix` that the filename ends with, in the order
the parsers registered them — not the longest match. That is exactly what
Sphinx core does for the host ``srcdir``, so mounted and host files behave
alike, but it does mean a multi-dot suffix can be partly stripped: with
``source_suffix`` ordered ``.rst``, ``.txt``, ``.rst.txt``, the file
``a.rst.txt`` becomes the docname tail ``a.rst`` because ``.txt`` matched
first. If a project registers overlapping suffixes, register the longer
ones first.

Bundle discipline
-----------------

Each mount should be a *self-contained* tree of source files: relative
``:doc:`` and ``:ref:`` references only, no ``..`` escapes, no reliance
on host project labels or substitutions. This guarantees the bundle is
reusable across host projects and that the IDE/language-server view of
the project matches the build view.

**dir** must not contain the host ``srcdir``. Nothing detects this, and
no collision warning can fire — the docnames differ, because every host page
simply gains a second docname under ``mount_at``. The symptom is the whole
host project appearing twice in the output. Point ``dir`` at the bundle, not
at an ancestor of the documentation tree.

**Single attachment point.** This rule applies to both directory and
file-list mounts: the extension auto-wires *only* the ``entry_doc``
into the host toctree (see :ref:`toctree-integration`). The mount's
*entry doc* is therefore responsible for making every other doc in
the bundle reachable, typically via its own ``toctree`` directive.
For a directory mount this is usually the mount's ``index.rst`` /
``index.md`` listing its siblings; for a file-list mount, one of the
listed files plays the same role and explicitly references the
others. If a doc inside the mount is not reachable from the entry
doc, Sphinx will warn about an orphan; that warning is the contract,
not the extension's job to suppress. The one exception is a file-list
mount with :ref:`attach_each <attach-each>`, which attaches every listed
file directly and so needs no entry doc to reach them.

.. _path-confinement:

Path confinement: keeping file references inside the bundle
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Directives that reference files — ``literalinclude``, ``include``,
``image``, ``figure``, ``csv-table`` (``:file:``), ``raw`` (``:file:``),
``graphviz``, and diagram extensions like ``uml`` (sphinxcontrib-plantuml)
and ``mermaid`` (sphinxcontrib-mermaid) — resolve **relative paths**
against the document's own location. For a mounted doc, that location is
the bundle on disk, so a relative reference resolves *inside the bundle*,
exactly as it would when the bundle is built standalone.

**What the bundle root is.** In directory mode it is ``dir`` — one root.
In file-list mode the mount has one root **per listed file**: the parent
directory of each entry in ``files``, with duplicates collapsed (several
entries in one directory contribute one root) and ``files`` order preserved.
A reference is inside the bundle when it is under **any** of them.

That union is deliberately bounded on both sides:

- It is wide enough to fix the asymmetry a per-*document* rule had. A mount
  listing ``rn/index.rst`` and ``rn/notes/2026-q1.rst`` has the roots
  ``rn/`` and ``rn/notes/``, so ``notes/2026-q1.rst`` may reference
  ``../shared.txt`` — that file is under ``rn/``, a directory the mount
  named. Confining each document to its own parent instead made the verdict
  depend on how deep a file happened to sit: the reference *down* from
  ``index.rst`` into ``notes/`` passed while the mirror-image reference *up*
  from ``notes/2026-q1.rst`` was rejected.
- It is narrow enough that it can never admit a directory you did not name.
  In particular it is **not** the common ancestor of the listed files. An
  ancestor is driven arbitrarily wide by the ``files`` list itself: two
  entries in sibling subtrees would make their shared parent the root, and
  two entries on unrelated filesystem branches would make it ``/`` — at
  which point ``path_check`` permits every file on the machine.

So listing files from unrelated trees widens the bundle by exactly those
trees' directories, and nothing else.

Bundle roots are always **resolved** (symlinks followed) before
comparison, and so are the references being checked, so a bundle reached
through a symlinked directory is not an escape. This is what makes the
Bazel layout work, where ``bazel-bin`` is itself a symlink. The flip side
is cosmetic: warnings name the *resolved* path, which for a Bazel mount is
a deep execroot path rather than the ``bazel-bin/...`` path you wrote.

Three reference shapes escape the bundle root:

- A **leading slash** (``/foo``) is "absolute from the source root" — for
  a mounted doc that is the **host** ``srcdir``, not the bundle. The same
  bundle would then read a different file in every host project.
- A path that **climbs out** with ``..`` (e.g. ``../../foo``) resolves to
  a location above the bundle root.
- A **symlink inside the bundle whose target is outside it**. The path
  written in the directive looks perfectly local; only its resolved form
  reveals the escape, which is why the warning says so explicitly.

Either way the bundle is no longer self-contained, and the outside file is
dragged into the host build — for asset directives Sphinx even copies it
into the host's ``_images`` / ``_downloads`` output, where it can collide
with the host project's own files.

``path_check`` controls the reaction, per mount:

.. code-block:: toml

   [[source.mounts]]
   dir = "/path/to/bundle"
   mount_at = "_generated/api-foo"
   path_check = "error"   # opt in to a hard stop without -W

- ``"warn"`` (default): log a ``mounts.path_escape`` warning naming the doc,
  the recorded and resolved paths, and the mount's bundle root(s). Like every
  other mount warning it is suppressible, and ``sphinx-build -W`` escalates it
  to a build failure — which is how a CI job turns it into a gate.
- ``"error"``: abort the build immediately instead. Use it where a hard stop
  is wanted without ``-W``.
- ``"off"``: disable the check for this mount.

``"warn"`` is the default because it is what the rest of this extension does:
:ref:`warnings-and-errors` states the doctrine that every mount-specific
problem is a typed, suppressible warning which ``-W`` turns into a failure,
and an escaping reference is a mount-specific problem like any other. A hard
default also could not deliver the guarantee it implied — see the second limit
below.

The check is directive-agnostic: it inspects the files Sphinx records as
dependencies of each mounted doc, so it covers every file-referencing
directive — including ones from third-party extensions — without
enumerating them.

Two limits are worth knowing, because both follow from *where* in the
build the check runs (``env-check-consistency``) and neither is a bug you
can configure away.

**It detects, it does not prevent.** By the time the check runs, the
offending doc has already been read and parsed, and its doctree and the
environment have been written to disk. For content directives
(``include``, ``literalinclude``, ``csv-table``, ``raw``) the outside
text is therefore already inside ``.doctrees``. What a *failing* build
prevents — ``path_check = "error"``, or the default under ``-W`` — is the
*output*: it stops before the write phase, so no escaped asset is copied into
``_images`` / ``_downloads`` and no HTML ships. Treat ``path_check`` as a gate
on what gets published, not as a sandbox on what gets read.

**It is not evaluated on a build that reads nothing.** Sphinx runs the
consistency checks only when at least one document was read
(``if updated_docnames:`` in its builder), so an unchanged re-run prints
``no targets are out of date`` and skips them. What that means for a second
build depends on the mode:

- With the default ``"warn"``, a re-run over an untouched tree is
  **silent** — it reports success for a project the previous run flagged. So
  make the *first* build the CI gate, and use ``-E`` (or a clean output
  directory) if a run has to be self-contained. The same applies under
  ``-W``: the escalation only fires on a build that actually re-read the doc.
- With ``path_check = "error"`` there is nothing to slip through: the raised
  error propagates out of the build, and Sphinx deletes the cached
  environment on its way out. Every subsequent run therefore starts from a
  fresh environment, reads everything, and fires the check again. The failure
  is sticky until it is fixed. That is the one thing ``"error"`` buys over
  the default plus ``-W``.

This is also why a hard *default* was the wrong choice: it read as a standing
invariant and never was one.

A build where only the *host* changed does still fire the check for every
mounted doc, in both modes, because dependencies persist in the environment
and the bundle roots are recomputed on each build.

.. note::

   ``path_check`` is about references that *leave* the bundle. It says
   nothing about a much likelier collision *inside* one: two bundles (or a
   bundle and the host) that both ship ``diagram.png`` produce
   ``_images/diagram.png`` and ``_images/diagram1.png``, and which side
   gets the unsuffixed name depends on the order Sphinx reads the
   documents. That order follows the docnames, so **renaming or adding a
   mount can change the published asset URL of a page that has nothing to
   do with it**. Sphinx assigns those names, not sphinx-mounts, so there
   is nothing to configure here — but give bundles distinctive asset names
   (or a per-bundle asset subdirectory) if anything deep-links to
   ``_images``.

.. _needs-file-references:

File references from Sphinx-Needs directives
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`Sphinx-Needs <https://sphinx-needs.readthedocs.io/>`__ contributes three
doc-relative file references, and they do not all behave alike. The example
project's ``showcase/needs`` bundle exercises all three, one page per
directive.

.. list-table::
   :widths: 26 22 26 26
   :header-rows: 1

   * - Reference
     - Resolved by
     - Sphinx dependency
     - Covered by ``path_check``
   * - ``needimport:: needs.json``
     - Sphinx ``relfn2path``
     - yes
     - yes
   * - ``needreport`` ``:template:``
     - Sphinx ``relfn2path``
     - no
     - no
   * - ``needuml`` / ``needarch`` PlantUML ``!include``
     - the PlantUML process
     - no
     - no

Only ``needimport`` records its file as a dependency, so only it is visible to
``path_check`` and to Sphinx's incremental rebuild. For the other two, keep
references bundle-relative by convention, and be aware that editing the
referenced file alone does not mark the page outdated — touch the ``.rst`` or
build with ``-E``.

The ``!include`` case has one further requirement. PlantUML resolves it in its
own working directory, which Sphinx-Needs must derive from the document's
**physical** source file; deriving it from the logical docname yields a
directory that does not exist for a mounted document, and the build fails with
the misleading ``plantuml command '...' cannot be run``. That needs
**sphinx-needs > 8.3.0** (see
`sphinx-needs#1749 <https://github.com/useblocks/sphinx-needs/issues/1749>`__).

One packaging note, unrelated to mounting: a ``needreport`` template is Jinja
*input*, not a document, yet conventionally carries an ``.rst`` suffix — so a
directory mount would walk it and publish an orphan page of unrendered Jinja.
List it under ``exclude``:

.. code-block:: toml

   [[source.mounts]]
   dir = "../showcase/needs"
   mount_at = "_generated/showcase/needs"
   exclude = ["report-template.rst"]

Files whose suffix is outside ``source_suffix`` — ``.puml``, ``.json`` — need no
exclude, since discovery never picks them up.

.. _warnings-and-errors:

Warnings and errors
-------------------

sphinx-mounts distinguishes two classes of problems:

**Hard errors — the configuration is unreadable.** Malformed TOML, wrong
types, unknown keys, and contradictory options are reported as
``Extension error`` messages and abort the build. sphinx-mounts cannot
proceed at all when the configuration is uninterpretable, so these
errors are deliberately *not* suppressible.

**Warnings — mount-specific problems.** Everything that affects a single
mount is reported as a warning, the build continues with the **whole
mount skipped** (so the host project is left completely untouched — no
partial mounts, no orphaned siblings, no dangling toctree references),
and the first provider of a docname wins. Every such warning carries the
warning ``type`` ``mounts`` with a per-problem ``subtype``, so it can be
identified as coming from sphinx-mounts, suppressed selectively (or all
at once), and escalated to a failed build:

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Warning type
     - Meaning
   * - ``mounts.attach_to_missing``
     - ``attach_to`` references a docname that does not exist
   * - ``mounts.deprecated_location``
     - the mounts array is declared as top-level ``[[mounts]]`` rather than
       ``[[source.mounts]]``; it still loads, identically
   * - ``mounts.docname_conflict``
     - a mount would shadow a docname already provided by the host
       project or an earlier mount, **or** two of the mount's own files
       map to one docname; the whole mount is skipped
   * - ``mounts.empty_docname``
     - a file-list entry's name is nothing but a registered suffix (e.g. a
       file called ``.rst``), so it has no docname; the whole mount is
       skipped
   * - ``mounts.ignored_option``
     - a file-list mount sets ``include`` or ``exclude``, which only
       directory mounts read; the keys have no effect
   * - ``mounts.missing_path``
     - a configured ``dir`` / ``files`` path does not exist on disk;
       the whole mount is skipped
   * - ``mounts.mount_at_occupied``
     - ``strict_mount_at`` is set and the host already has a directory
       at the mount point; the whole mount is skipped
   * - ``mounts.path_escape``
     - a mounted doc references a file outside its bundle root (the default
       ``path_check = "warn"``; ``"error"`` aborts instead of warning)
   * - ``mounts.toctree_index``
     - ``toctree_index`` exceeds the number of toctrees in the
       ``attach_to`` document; the mount is left unwired and its docs are
       marked as orphans, so no ``toc.not_included`` follows
   * - ``mounts.unknown_suffix``
     - a file-list entry has no extension registered in
       ``source_suffix``; the whole mount is skipped

.. _suppressing-mount-warnings:

Suppressing and escalating mount warnings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Mount warnings are regular Sphinx warnings, so the standard Sphinx
mechanisms apply. Suppress one problem (or all of them) in ``conf.py``
via :confval:`suppress_warnings <sphinx:suppress_warnings>`:

.. code-block:: python

   suppress_warnings = [
       "mounts",                  # every sphinx-mounts warning
       "mounts.docname_conflict", # …or just this one problem
   ]

Sphinx matches warning types exactly (``type``, ``type.*``, or
``type.subtype``). Listing ``"mounts"`` silences every sphinx-mounts
warning at once, while ``"mounts.docname_conflict"`` silences only that
one; individual subtypes and the whole extension can be mixed freely.

To turn any mount problem into a hard build failure instead, build with
``sphinx-build -W`` (warnings as errors) — the warning then fails the
build exactly where the problem occurs. This is the escalation path for
users who want mount conflicts or missing bundles to break CI rather
than degrade the docs.
