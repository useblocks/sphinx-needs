needuml
=======

SHOWCASE_NEEDUML

``needuml`` renders a PlantUML diagram from directive content. The content may
``!include`` another PlantUML file, which the PlantUML process resolves against
its **working directory** — and Sphinx-Needs derives that from the source file
of the document holding the directive. A bundle-relative ``!include``
therefore resolves against the bundle root, mounted or not.

This is the one Sphinx-Needs path that Sphinx never sees: ``!include`` is
handled inside PlantUML, so no dependency is recorded for it. Two consequences
worth knowing when you ship diagrams in a bundle:

- editing ``arch-common.puml`` alone does not mark these pages outdated, so an
  incremental rebuild will not pick the change up (touch the ``.rst``, or build
  with ``-E``);
- ``path_check`` cannot see the reference either, so an ``!include`` that
  escapes the bundle root is *not* caught. Keep such includes bundle-relative
  by convention.

.. needuml::

   !include arch-common.puml

   component "needuml page" as Page
   Page --> BundleLibrary : "!include"
