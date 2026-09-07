needreport
==========

SHOWCASE_NEEDREPORT

``needreport`` renders a Jinja template, and its ``:template:`` option is
resolved **relative to the containing document** via ``relfn2path`` — the same
mechanism ``needimport`` uses, so it behaves identically under a mount.

Shipping the template inside the bundle is what makes the bundle portable: the
built-in default template emits ``dropdown`` directives and would require the
host project to load ``sphinx-design``. With its own template the bundle needs
nothing from the host beyond Sphinx-Needs itself.

.. needreport::
   :types:
   :template: report-template.rst

.. note::

   Sphinx-Needs does not record a dependency on the template file, so — like
   the PlantUML ``!include`` — editing ``report-template.rst`` alone will not
   mark this page outdated, and ``path_check`` cannot see the reference.
