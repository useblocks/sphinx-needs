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
      [[mounts]]
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
file referenced by ``mounts_from_toml``), then swaps in a subclass of
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

   [[mounts]]
   dir = "/path/to/bazel-bin/docs/api-foo"
   mount_at = "_generated/api-foo"
   attach_to = "index"          # extend the toctree in index.rst

The host's ``index.rst`` can then ship with an empty (or shorter)
toctree; the extension appends ``_generated/api-foo/index`` to it during
the build. See :ref:`toctree-integration` for picking a specific toctree
in a multi-toctree host doc and for choosing a non-``index`` entry file.

Incremental rebuilds
--------------------

Sphinx's standard mtime-based change detection works for mounted files
because the docname-to-path mapping is rebuilt every time
``project.discover()`` runs. New files appear, deleted files disappear,
and changed files are re-read. No extra configuration is required.

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
