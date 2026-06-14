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
  `sphinx-codelinks`_, ``[[mounts]]`` for sphinx-mounts, etc.). The
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

**Mounting never shadows host files.** On Linux, mounting onto a
non-empty directory hides the original contents until you unmount.
In sphinx-mounts, a mounted file that would produce the same docname
as a host file is **rejected at build time** with a
``docname conflict`` error. Nothing is silently hidden; conflicts
have to be resolved by the author (rename one side, narrow the
mount's ``include`` / ``exclude``, or move the host file).

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

``ubproject.toml`` declares a top-level ``[[mounts]]`` array of tables.
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
   [[mounts]]
   dir = "/abs/path/to/bazel-bin/docs/api-foo"
   mount_at = "_generated/api-foo"

   [[mounts]]
   dir = "../shared-bundles/api-bar"
   mount_at = "_generated/api-bar"
   include = ["**/*.rst"]                # optional allowlist
   exclude = ["internal/**", "draft.rst"]
   gitignore = false                     # opt out of the bundle's .gitignore

   # File-list mode: cherry-pick individual files.
   [[mounts]]
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
       :ref:`path anchor <path-anchoring>`. Each listed file must
       exist at build time and have an extension Sphinx knows about;
       an unrecognised extension is an error (the user explicitly
       asked for the file, so silently skipping it would be wrong).
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
     - Host docname whose toctree should receive the mount entry. When
       set, the extension wires ``{mount_at}/{entry_doc}`` into that
       doc's toctree automatically. See
       :ref:`toctree-integration` below.
   * - ``toctree_index``
     - no
     - 0-based index selecting *which* toctree in ``attach_to`` to
       extend, in document order. Defaults to ``0`` (the first
       toctree). Ignored unless ``attach_to`` is set.
   * - ``entry_doc``
     - no
     - Mount-relative docname of the entry file to wire into the host
       toctree. Defaults to ``"index"``.
   * - ``strict_mount_at``
     - no
     - Whether to fail the build if the host project has a directory
       at ``<srcdir>/<mount_at>/``. Defaults to ``false``. See
       :ref:`strict-mount-at` for the trade-off and when to enable it.
       Incompatible with a root mount (``mount_at`` omitted).
   * - ``path_check``
     - no
     - How to react when a directive inside a mounted doc references a
       file outside the bundle root. One of ``"error"`` (default),
       ``"warn"``, or ``"off"``. See :ref:`path-confinement` below.

.. _root-mount:

Mounting at the host project root
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Omitting ``mount_at`` mounts the bundle at the host's project root.
The common shape is pulling an entire directory of RST into the host
project as-is, with no prefix renaming:

.. code-block:: toml

   [[mounts]]
   dir = "./api"
   # mount_at omitted — files under ./api appear as bare docnames
   # (e.g. ./api/tutorial.rst → docname "tutorial").

The host project is responsible for ensuring no docname collides with
its own files. If a bundle file would shadow a host doc, sphinx-mounts
raises a ``docname conflict`` error at build time.

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
directory at ``<srcdir>/<mount_at>/`` an immediate build error:

.. code-block:: toml

   [[mounts]]
   dir = "/path/to/bundle"
   mount_at = "_generated/api-foo"
   strict_mount_at = true

The check fires before any file discovery, with a message naming
the offending host path. Only the leaf path is inspected; a host
directory at a *parent* of ``mount_at`` (e.g. ``_generated/``) is
fine — the mount slots a virtual subdirectory under a real host
section dir, which is a normal pattern. The flag is mode-agnostic:
file-list mounts honour it the same way directory mounts do, since
both share the ``mount_at`` docname prefix.

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

   [[mounts]]
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
during the build. When the mount is absent, ``mounts_from_toml`` resolves
no mounts and the host builds cleanly with whatever was already in the
toctree.

Picking a specific toctree
~~~~~~~~~~~~~~~~~~~~~~~~~~

A host doc may have several ``toctree`` directives — for example, a
top-level navigation toctree plus per-section sub-toctrees. Use
``toctree_index`` (0-based, document order) to pick the right one:

.. code-block:: toml

   [[mounts]]
   dir = "/path/to/api-foo"
   mount_at = "_generated/api-foo"
   attach_to = "index"
   toctree_index = 1            # extend the second toctree in index.rst

If ``toctree_index`` exceeds the number of toctrees actually present in
``attach_to``, the build fails with an explicit ``ExtensionError`` —
silent misconfiguration would leave the mount unreferenced.

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

   [[mounts]]
   dir = "../shared-bundles/api-bar"
   mount_at = "_generated/api-bar"
   attach_to = "index"
   entry_doc = "overview"

The resulting docname inserted into the toctree is then
``_generated/api-bar/overview``.

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

If both ``ubproject.toml`` and ``mounts`` in ``conf.py`` are present, the
TOML file wins.

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

Absolute paths are taken as-is in both cases. A path-resolution rule
that surprises is worse than one that is verbose, so prefer absolute
paths (or the TOML-anchored form) when a project is bundled across
unusual directory layouts.

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
   [[mounts]]
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
- Hidden entries (dotfiles, ``.git/``) are skipped.
- ``include`` entries are added as positive gitignore-style overrides
  (allowlist): if non-empty, only files matching at least one
  pattern reach Sphinx. ``exclude`` entries are added as negated
  overrides (``!pattern``). Both lists are evaluated relative to
  ``dir``. Patterns like ``**/*.rst``, ``internal/**``, or
  ``draft.rst`` work as you would expect from a ``.gitignore`` file.

Bundle discipline
-----------------

Each mount should be a *self-contained* tree of source files: relative
``:doc:`` and ``:ref:`` references only, no ``..`` escapes, no reliance
on host project labels or substitutions. This guarantees the bundle is
reusable across host projects and that the IDE/language-server view of
the project matches the build view.

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
not the extension's job to suppress.

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

Two reference shapes escape the bundle root:

- A **leading slash** (``/foo``) is "absolute from the source root" — for
  a mounted doc that is the **host** ``srcdir``, not the bundle. The same
  bundle would then read a different file in every host project.
- A path that **climbs out** with ``..`` (e.g. ``../../foo``) resolves to
  a location above the bundle root.

Either way the bundle is no longer self-contained, and the outside file is
dragged into the host build — for asset directives Sphinx even copies it
into the host's ``_images`` / ``_downloads`` output, where it can collide
with the host project's own files.

``path_check`` controls the reaction, per mount:

.. code-block:: toml

   [[mounts]]
   dir = "/path/to/bundle"
   mount_at = "_generated/api-foo"
   path_check = "error"   # default — fail the build on any escape

- ``"error"`` (default): an escaping reference fails the build, naming the
  doc, the resolved path, and the bundle root.
- ``"warn"``: log a warning instead (escalates to an error under
  ``sphinx-build -W``).
- ``"off"``: disable the check for this mount.

The check is directive-agnostic: it inspects the files Sphinx records as
dependencies of each mounted doc, so it covers every file-referencing
directive — including ones from third-party extensions — without
enumerating them.
