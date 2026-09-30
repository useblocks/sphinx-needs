.. _variants-example:

ubCode Variants Example
=======================

A single "150%" source that describes every build variant at once. Field
values are resolved per build from the project's *variant data*
(``variants.json`` plus the inline ``[needs.variant_data]`` overrides in
``ubproject.toml``) and from ``build_tags``. See ``README.md`` for the
per-variant build workflow.

.. req:: Networking subsystem
   :id: REQ_NET
   :status: <<[var.platform == "windows"]: windows_active, other_active>>
   :platform_note: Built for <{ var.platform }>

   ``status`` is selected by a *variant function* on ``var.platform``;
   ``platform_note`` embeds a *variant-data reference*.

.. req:: Logging subsystem
   :id: REQ_LOG
   :status: <<is_html: documented, undocumented>>

   Uses the named variant ``is_html``, which checks ``build_tags``.

.. req:: Storage subsystem
   :id: REQ_STORE
   :status: <<["arm" in var.archs]: arm_supported, arm_unsupported>>
   :platform_note: Compiler is <{ var.build.compiler }>

   Demonstrates array membership and a nested variant-data reference.
