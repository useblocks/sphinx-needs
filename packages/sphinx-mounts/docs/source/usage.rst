Usage
=====

A minimal setup
---------------

1. Add ``sphinx_mounts`` to ``extensions`` in ``conf.py``:

   .. code-block:: python

      # conf.py
      extensions = ["sphinx_mounts"]

2. Describe your mounts in ``ubproject.toml`` next to ``conf.py``:

   .. code-block:: toml

      # ubproject.toml
      [[source.mounts]]
      dir = "/abs/path/to/bazel-bin/docs/api-foo"
      mount_at = "_generated/api-foo"

3. Reference mounted docs from your host project's ``index.rst`` like any
   other docname:

   .. code-block:: rst

      .. toctree::
         :maxdepth: 2

         _generated/api-foo/index

That is it — there is no third step to copy or stage files. ``sphinx-build``
reads the bundle directly from ``dir``.

How it works
------------

When a build starts, ``sphinx-mounts`` loads ``ubproject.toml`` (or the
file referenced by ``sources_from_toml``), then swaps in a subclass of
:class:`sphinx.project.Project` whose ``discover()`` does two things:

1. The normal srcdir walk, populating docnames from your host project.
2. A walk over each configured mount source, registering each file
   whose extension matches the project's ``source_suffix`` (``.rst`` by
   default; ``.md`` when ``myst_parser`` is loaded; etc.) under the
   configured ``mount_at`` prefix with the file's **absolute** path.

When Sphinx later calls ``project.doc2path(docname, absolute=True)``, the
absolute external path wins (a ``pathlib`` detail — ``srcdir / abs_path``
returns ``abs_path`` when the right operand is absolute), and Sphinx
reads the file directly from its external location.

For the full event sequence, the rules used to compute a docname from
``mount_at`` plus a source path, and the discipline mounted sources
should follow when cross-referencing, see :doc:`integration`.

Referencing mounted documents
-----------------------------

Mounted documents look like any other docname. Reference them from the
host project's ``toctree`` and via ``:doc:`` / ``:ref:`` as usual:

.. code-block:: rst

   .. toctree::
      :maxdepth: 2

      _generated/api-foo/index
      _generated/api-bar/index

   See the :doc:`_generated/api-foo/tutorial` for a walkthrough.

Wiring a mount automatically: ``attach_to``
-------------------------------------------

A hand-written toctree entry breaks the host build if the mount is ever
absent (a developer hasn't run the upstream build, CI hasn't fetched the
bundle). Set ``attach_to`` to make sphinx-mounts inject the entry at
build time only when the mount actually resolves:

.. code-block:: toml

   [[source.mounts]]
   dir = "/path/to/bazel-bin/docs/api-foo"
   mount_at = "_generated/api-foo"
   attach_to = "index"          # extend the toctree in index.rst

The host's ``index.rst`` can then ship with an empty (or shorter)
toctree; the extension appends ``_generated/api-foo/index`` to it during
the build. See :ref:`toctree-integration` for picking a specific toctree
in a multi-toctree host doc and for choosing a non-``index`` entry file.

.. _incremental-rebuilds:

Incremental rebuilds
--------------------

Sphinx's standard mtime-based change detection works for mounted files
because the docname-to-path mapping is rebuilt every time
``project.discover()`` runs. New files appear, deleted files disappear,
and changed files are re-read. No extra configuration is required.

``attach_to`` wiring tracks those appearances and disappearances as well.
Because the mapping is rebuilt on every build, the extension can compare
the set of entries each mount *would* wire against what it wired last
time, and ask Sphinx to re-read the ``attach_to`` document when the two
differ. So both directions converge on the build where the change
happened, with no ``-E``:

- A bundle whose entry doc **appears** — the upstream build finally ran —
  is wired into the host toctree on that build.
- A bundle whose entry doc **disappears** is unwired on that build. No
  dead link is left in the output and no repeating "toctree contains
  reference to non-existing document" warning accumulates.

Only documents named by an ``attach_to`` are re-read this way, and only
when that mount's contribution actually changed, so an unrelated bundle
churning does not drag host pages into the rebuild.

.. important::

   The guarantee covers documents reached through ``attach_to``, and only
   when the ``attach_to`` target itself exists. A mounted docname that a host
   page references by **hand** — written into a toctree in the source — is
   not covered: nothing marks that host page outdated when the mount
   disappears, so its dead link persists *silently*. The
   ``toc.not_readable`` warning is **not** re-emitted, because Sphinx
   re-resolves a toctree only when the page is re-read — so even ``-W``
   passes. The warning appears, and the dead link goes away, only once the
   page is touched or ``-E`` is used.

   That residue is Sphinx's own behaviour, not something mounting
   introduces: deleting an ordinary host document leaves exactly the same
   dead link in exactly the same way. If you want the automatic convergence,
   let ``attach_to`` do the wiring rather than naming mounted docnames by
   hand.

One consequence is worth knowing, because it looks like the extension
doing extra work: a build that *only removes* documents used to persist
nothing at all. Sphinx pickles the environment and runs its consistency
checks only when at least one document was read, so such a build
recomputed the same "1 removed" every time. Re-reading the ``attach_to``
document is what lets that build save its environment and settle.

What incremental rebuilds do **not** cover: the consistency checks —
including :ref:`path_check <path-confinement>` — are skipped entirely on a
build that reads no document at all. See the note in that section.

Caveats
-------

- **Sphinx-autobuild** only watches ``srcdir``. External sources changing
  will not trigger an auto-rebuild. For build-system-driven flows (Bazel),
  let the build system invoke ``sphinx-build`` when its inputs change.
- Sphinx's own ``exclude_patterns`` in ``conf.py`` is evaluated against
  ``srcdir`` and does not filter mounted files. Use the per-mount
  ``include`` and ``exclude`` lists in ``ubproject.toml`` instead.
- The extension reads ``sphinx.project.Project._docname_to_path``
  (a private attribute). The Sphinx project may refactor it. This
  extension is tested against Sphinx 7.4, 8.x, 9.x.
