Basic edition reference
=========================

REFERENCE_BASIC_INDEX_MARKER

This bundle is a checked-in **edition** bundle: it exists only in the
basic variant of the example (see ``[needs.variant_data]`` in
``docs/ubproject.toml``). Its mount entry carries
``if = "var.edition == 'basic'"``, so the pro build gates the whole
bundle off — this page has no docname there at all.

The two edition bundles (basic / pro) live side by side at **distinct**
``mount_at`` prefixes, exactly as the docs recommend, so the gated
bundle's attribution survives and ``sphinx-build -W`` passes in either
variant. The live bundle's index is wired into the host toctree via
``attach_to``.

.. toctree::
   :maxdepth: 1

   reference