Example host project
====================

INDEX_PAGE_MARKER

The host owns its own structure: this page and its toctree below are
hand-written. Two Bazel-generated bundles are mounted from
``ubproject.toml`` using the two supported wiring styles:

- ``api-foo`` (RST) uses ``attach_to = "index"`` and ``entry_doc =
  "index"``, so ``sphinx-mounts`` injects its entry doc into the
  toctree below at build time. The toctree directive does not name
  ``api-foo``.
- ``api-bar`` (Markdown) sets no ``attach_to``, so the host
  references its entry doc by hand below.

With the bundles absent, ``installation`` still renders. The
``api-bar`` manual reference would surface as an unresolved toctree
entry; ``api-foo`` would simply not appear.

.. toctree::
   :maxdepth: 2

   installation
   _generated/api-bar/index
