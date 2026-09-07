needimport
==========

SHOWCASE_NEEDIMPORT

``needimport`` reads a ``needs.json`` addressed **relative to the importing
document**, through Sphinx's own ``relfn2path``. Because ``relfn2path`` asks
the project where the document physically lives, a mounted document gets the
bundle's real directory and the bundle-relative path below just works.

``imported-needs.json`` here stands in for what another Sphinx-Needs project
exported with its ``needs`` builder and this bundle vendored — in a Bazel setup,
copied in by the rule that produced the bundle.

Unlike the ``!include`` on the previous two pages, this one *is* registered as
a Sphinx dependency, so editing ``imported-needs.json`` marks this page
outdated and ``path_check`` would catch an import that escaped the bundle root.

.. needimport:: imported-needs.json

The imported needs are ordinary needs afterwards — filterable, linkable and
part of the same graph as the ones the bundle declares itself:

.. needtable::
   :filter: "imported" in tags
   :columns: id;title;status
   :style: table
