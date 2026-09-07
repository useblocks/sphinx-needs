needarch
========

SHOWCASE_NEEDARCH

``needarch`` is ``needuml`` scoped to the need it is nested in: the same
bundle-relative ``!include`` works, and the surrounding need is available to
the diagram through the ``need()`` Jinja function.

.. spec:: Component view of the bundle
   :id: SN_SPEC_ARCH
   :status: open
   :links: SN_SPEC_PUML

   .. needarch::

      !include arch-common.puml

      component "{{ need().id }}" as Self
      Self --> BundleLibrary : "!include"
