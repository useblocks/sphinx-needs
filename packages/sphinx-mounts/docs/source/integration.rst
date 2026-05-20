Integration with Sphinx
=======================

This page goes a layer below :doc:`usage` and documents how
sphinx-mounts plugs into Sphinx's build pipeline, how docnames are
derived from mount configuration, and the discipline mounted source
trees should follow to stay reusable.

Event handlers
--------------

The extension registers five event handlers in ``setup()``. Sphinx
event priority is "lower number runs earlier"; the default is 500.

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Event
     - Priority
     - Purpose
   * - ``config-inited``
     - 400
     - ``_on_load_toml`` resolves ``mounts_from_toml`` against ``confdir``
       and replaces ``config.mounts`` with the array parsed from the TOML
       (paths anchored to the TOML's own directory). Runs before
       validation so the validator sees the final list.
   * - ``config-inited``
     - 500
     - ``_on_config_inited`` runs ``parse_mounts`` on ``config.mounts``,
       resolves relative paths against ``confdir`` (for legacy
       ``conf.py``-declared mounts), checks that ``dir`` directories
       or each ``files`` entry exist, and caches the validated tuple of
       ``MountConfig`` instances on the application object.
   * - ``builder-inited``
     - default
     - ``_on_builder_inited`` replaces ``app.project`` with a
       ``_MountAwareProject`` subclass that carries the parsed mount
       list. The build environment is repointed at the new project so
       the subsequent ``env.find_files`` → ``project.discover()`` call
       runs through it.
   * - ``doctree-read``
     - **400**
     - ``_on_doctree_read`` extends or creates a toctree in any host
       doc whose docname matches a mount's ``attach_to`` field. See
       :ref:`toctree-integration` for the full rules, and the note
       below for why the priority is non-default.
   * - ``env-check-consistency``
     - default
     - ``_on_check_consistency`` emits a warning if a mount's
       ``attach_to`` does not resolve to a real docname after every
       doc has been read.

.. _doctree-read-priority:

Why ``doctree-read`` runs at priority 400
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sphinx ships an environment collector — ``TocTreeCollector`` — that
also subscribes to ``doctree-read``. Its
``process_doc(app, doctree)`` populates ``app.env.included`` from the
toctrees it finds in the doctree, and ``app.env.included`` is what
Sphinx's later ``check_consistency`` step uses to emit the
``toc.not_included`` warning ("document isn't included in any
toctree"). The collector runs at the default priority of 500.

If ``_on_doctree_read`` also ran at 500, listener order would be
decided by registration order: ``TocTreeCollector`` is connected
during Sphinx app initialisation (before extensions load), and our
extension's ``setup()`` runs later — so the collector would handle
each doctree *first* and our toctree mutation would land after
``env.included`` was already populated from the unmodified node. A
build run with ``sphinx-build -W`` would then flag every entry doc
``attach_to`` injected as not-included, even though the mutated
toctree node visibly contains it.

Registering at priority **400** places our handler ahead of every
default-priority listener. The collector sees the mutated toctree,
``env.included`` reflects every injected entry, and the consistency
check passes cleanly — even with warnings-as-errors. The fix is the
small reason ``attach_to`` works under ``-W`` and the
``tests/example/`` end-to-end test runs green.

The mount-aware project
-----------------------

:class:`sphinx.project.Project` is the in-memory model of "which
docnames exist and where do they live on disk". sphinx-mounts
subclasses it:

.. code-block:: python

   class _MountAwareProject(Project):
       def discover(self, exclude_paths=(), include_paths=("**",)):
           docs = super().discover(exclude_paths, include_paths)
           for mount in self._mounts:
               docs |= _attach_mount(self, mount)
           return docs

After ``super().discover()`` populates docnames from the host
``srcdir``, every configured mount is walked and its files are
registered with **absolute** filesystem paths in the project's
``_docname_to_path`` dictionary.

The absolute-path trick
~~~~~~~~~~~~~~~~~~~~~~~

Sphinx resolves a docname to a path with
``project.doc2path(docname, absolute=True)``, which internally
computes:

.. code-block:: python

   srcdir / self._docname_to_path[docname]

The relevant detail is :class:`pathlib.Path`'s ``__truediv__``
behaviour:

.. code-block:: pycon

   >>> from pathlib import Path
   >>> Path("/some/srcdir") / Path("/abs/external/file.rst")
   PosixPath('/abs/external/file.rst')

When the right operand is absolute, the left operand is *discarded*.
So storing an absolute external path in ``_docname_to_path`` causes
Sphinx to read from that external location transparently, without any
copy, symlink, or staging step. This single observation is the entire
mechanism that lets sphinx-mounts work without touching any other part
of Sphinx.

.. note::

   The extension intentionally writes to private (single-underscore)
   attributes on :class:`sphinx.project.Project` —
   ``_docname_to_path`` and ``_path_to_docname``. The use is gated to
   one module (``src/sphinx_mounts/mounter.py``) and is documented in
   code with a pointer at the upstream class. If Sphinx ever changes
   this contract, the breakage will be local.

.. _docname-mapping:

Docname mapping
---------------

A *docname* is the canonical identifier Sphinx uses for a document.
It is a forward-slash-separated path **without** the source suffix.
``mount_at`` is the prefix the mount contributes; the docname tail
depends on the mount mode.

Directory mode
~~~~~~~~~~~~~~

For each file under ``dir`` whose extension matches the project's
``source_suffix``:

.. code-block:: text

   docname_tail = relative_path_under_dir (POSIX-style)
                  with the matched suffix stripped
   docname      = f"{mount_at}/{docname_tail}"

Worked examples, assuming ``mount_at = "_generated/api-foo"`` and a
project whose ``source_suffix`` is ``{".rst": ..., ".md": ...}``:

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Source file (under ``dir``)
     - Resulting docname
   * - ``index.rst``
     - ``_generated/api-foo/index``
   * - ``intro.rst``
     - ``_generated/api-foo/intro``
   * - ``sub/details.rst``
     - ``_generated/api-foo/sub/details``
   * - ``guides/v2/migration.md``
     - ``_generated/api-foo/guides/v2/migration``
   * - ``unknown_extension.txt``
     - *(skipped silently)*

Subdirectories under ``dir`` are preserved in the docname, so the
on-disk layout and the docname tree mirror each other.

File-list mode
~~~~~~~~~~~~~~

For each path in the ``files`` list:

.. code-block:: text

   docname_tail = basename(file) with the matched suffix stripped
   docname      = f"{mount_at}/{docname_tail}"

The file's parent directories are deliberately discarded — file-list
mode is for cherry-picking individual documents, and a flat namespace
under ``mount_at`` is what the user is asking for. Two files with the
same basename would collide on docname and raise.

Worked examples, again with ``mount_at = "_generated/notes"``:

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Listed file
     - Resulting docname
   * - ``/abs/path/release-notes/2026-q1.md``
     - ``_generated/notes/2026-q1``
   * - ``/abs/path/release-notes/q1/recap.md``
     - ``_generated/notes/recap``
   * - ``../another/dir/intro.rst``
     - ``_generated/notes/intro``

Unlike directory mode, a listed file with an extension that does not
match ``source_suffix`` is **an error**, not a silent skip — the user
asked for that file by name, so silently ignoring it would be wrong.

Suffix handling
~~~~~~~~~~~~~~~

Suffix matching iterates whatever Sphinx has registered in
:confval:`sphinx:source_suffix`:

- ``.rst`` is the default.
- ``.md`` is registered when ``myst_parser`` is loaded; mounting
  Markdown bundles "just works" once the host enables the parser.
- Multi-dot suffixes (e.g. a parser registering ``.rst.txt``) are
  matched by full-string suffix comparison, so the docname tail
  strips the entire matched suffix.
- Any parser extension a project plugs in is honoured the same way.
  See :ref:`source-formats`.

Cross-document references
-------------------------

Inside the mount
~~~~~~~~~~~~~~~~

Once a file is mounted, its docname is indistinguishable from any
other docname in the project. ``:doc:`` and ``:ref:`` work as usual.
Within a bundle, the recommended form is **relative** docname
references:

.. code-block:: rst

   See the :doc:`details` page for the calling convention.

When this directive lives in ``intro.rst`` inside the bundle, the
unqualified ``details`` resolves to the sibling ``details`` docname
in the same directory — independently of the ``mount_at`` prefix
the host project happens to use.

From the host into the mount
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The host project references mounted docs by their full docname
(``mount_at`` prefix + tail). This is what a ``toctree`` entry, an
explicit ``:doc:`` link, or an ``attach_to`` injection produces:

.. code-block:: rst

   .. toctree::

      _generated/api-foo/index

   The :doc:`_generated/api-foo/details` page shows the parameters.

.. _anti-pattern-back-references:

Anti-pattern: mounted sources linking back to the host
------------------------------------------------------

A mounted document **can** reference host project docnames or labels.
Sphinx will resolve those references the same way it resolves any
others, because by the time resolution runs there is only one docname
space. **You should not do this.**

A bundle that references back into the host project becomes coupled
to that host:

- **Circular dependency.** The host depends on the bundle for content;
  the bundle now depends on the host's structure for its own
  cross-references to resolve. Any time either side moves a doc or
  renames a label, the other side breaks.
- **Non-portable bundles.** A bundle that mentions
  ``:doc:`/guides/installation``` works in one host project and 404s
  in every other. The bundle has effectively become host-specific
  documentation that happens to live in another tree.
- **Maintenance noise.** The bundle author can no longer review their
  own RST in isolation; they need to know what every host that
  consumes the bundle calls its own docs.
- **IDE confusion.** Tools that resolve cross-references against the
  ``ubproject.toml`` of whichever project is open will succeed in one
  workspace and fail in another, even though the source on disk is
  identical.

The correct mental model is **strictly one-way** linking:

.. code-block:: text

      ┌──────────────────────────┐
      │       host project       │
      │   (index.rst, guides/,   │
      │    toctrees, refs)       │
      └────────────┬─────────────┘
                   │  links DOWN
                   ▼
      ┌──────────────────────────┐
      │   mounted source tree    │
      │  (self-contained, only   │
      │  uses relative :doc:/    │
      │  :ref: within itself)    │
      └──────────────────────────┘

Treat the bundle as a *library* of documentation:

- A library publishes its API docs as a stand-alone artefact.
- Consumers (host projects) link to that library's docs.
- The library never references the consumer back.

Concretely, when authoring a mounted bundle:

- Use only **relative** ``:doc:`` references that stay inside the
  bundle.
- Use only ``:ref:`` labels defined inside the bundle.
- Do not include ``..`` segments or anchored docnames that walk out
  of the bundle's directory.
- Do not rely on substitutions, ``:rst-prolog:``, ``:rst-epilog:``,
  or other implicit context provided by the host's ``conf.py``.

The payoff is that the bundle can be:

- Developed and tested in isolation (e.g. with its own minimal
  ``conf.py``).
- Reused unchanged across multiple host projects.
- Versioned independently of any single host.
- Rendered by the host's IDE / language server consistently with the
  full build, because nothing in the bundle depends on host-specific
  context.

sphinx-mounts does not yet enforce these constraints with a linter;
following them is part of the same :ref:`bundle discipline
<file-discovery>` the extension expects.
