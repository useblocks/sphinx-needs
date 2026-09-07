sphinx-needs
============

SHOWCASE_NEEDS_INDEX

Unlike the other showcase bundles — one directive each — this one is a
kitchen sink for `Sphinx-Needs <https://sphinx-needs.readthedocs.io/>`__,
because Sphinx-Needs contributes **three** directives that resolve a path
relative to the document containing them. Each gets its own page below,
sitting next to the file it reads:

.. list-table::
   :widths: 20 30 50
   :header-rows: 1

   * - Page
     - Reads
     - How the path is resolved
   * - :doc:`needuml`
     - ``arch-common.puml``
     - PlantUML ``!include``, relative to the working directory
       Sphinx-Needs derives from the document's source file.
   * - :doc:`needarch`
     - ``arch-common.puml``
     - Same as ``needuml`` — ``needarch`` is ``needuml`` scoped to the
       need it is nested in.
   * - :doc:`needimport`
     - ``imported-needs.json``
     - Sphinx's ``relfn2path``, i.e. relative to the importing document.
   * - :doc:`needreport`
     - ``report-template.rst``
     - Sphinx's ``relfn2path``, same as ``needimport``.

Every one of those paths is bundle-relative, so the bundle stays
self-contained and survives ``path_check`` once mounted.

The needs below are the bundle's own; the pages that follow link to them, so
the whole traceability graph lives inside the bundle too.

.. req:: A mounted bundle resolves paths against its own root
   :id: SN_REQ_PATHS
   :status: open
   :tags: mounts

   Every file a mounted document references must be found from the
   document's **physical** location on disk, not from its logical docname —
   the two differ for a mounted document, and only the former exists.

.. spec:: Ship a bundle-local PlantUML library
   :id: SN_SPEC_PUML
   :status: open
   :links: SN_REQ_PATHS

   ``arch-common.puml`` lives next to the pages that ``!include`` it, so the
   diagram source travels with the bundle instead of being pulled from the
   host project.

.. toctree::
   :maxdepth: 1

   needuml
   needarch
   needimport
   needreport
