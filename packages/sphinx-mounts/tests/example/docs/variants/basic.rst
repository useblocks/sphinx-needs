Basic edition
=============

VARIANT_BASIC_PAGE_MARKER

This host page exists **only in the basic variant**. A
``[[source.variant_sources]]`` rule gates it by glob (see
``docs/ubproject.toml``). In the pro build this file has no docname at
all — but the host ``index`` toctree still names it, and sphinx-mounts
downgrades that reference to INFO (``[mounts.variant_excluded_reference]``),
so ``sphinx-build -W`` still passes in either variant.

The basic edition's reference bundle is mounted at
``_generated/reference/basic`` and wired into the host ``index`` toctree via
``attach_to``; its entry doc is reachable at
:doc:`/_generated/reference/basic/index`.