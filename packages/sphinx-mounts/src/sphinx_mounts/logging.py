"""Typed-warning helpers for sphinx-mounts.

Every warning this extension emits carries a Sphinx warning ``type`` of
``mounts`` with a per-problem ``subtype``, so the console shows
``[mounts.<subtype>]`` and users can suppress at either granularity via
Sphinx's ``suppress_warnings`` config:

.. code-block:: python

   suppress_warnings = [
       "mounts",                    # suppress every sphinx-mounts warning
       "mounts.docname_conflict",   # …or just this one problem
   ]

Sphinx matches warning types exactly (``type``, ``type.*``, or
``type.subtype``), so ``type="mounts"`` with a ``subtype`` gives group
suppression (``"mounts"`` silences all) a plain single-segment type
would not. Non-suppressed warnings are counted by Sphinx and escalate to
a failed build under ``sphinx-build -W`` (``warningiserror``), which is
how users turn "soft" mount problems into hard build failures when they
want to.

Config *validation* errors (malformed TOML, wrong types, unknown keys)
deliberately stay hard ``ExtensionError`` failures instead of warnings —
sphinx-mounts cannot proceed at all when the configuration is unreadable,
and such errors must not be suppressible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from sphinx import version_info

if TYPE_CHECKING:
    from sphinx.util.logging import SphinxLoggerAdapter

#: Warning subtypes known to sphinx-mounts. Keep sorted — adding a new
#: subtype should be a visible, reviewable diff.
WarningTopics = Literal[
    "attach_to_missing",
    "docname_conflict",
    "missing_path",
    "mount_at_occupied",
    "path_escape",
    "toctree_index",
    "unknown_suffix",
]

#: Warning ``type`` shared by every sphinx-mounts warning. Combined with a
#: ``subtype``, ``suppress_warnings = ["mounts"]`` silences all of them.
WARNING_TYPE = "mounts"


def log_warning(
    logger: SphinxLoggerAdapter,
    message: str,
    topic: WarningTopics,
    *,
    location: str | None = None,
) -> None:
    """Emit a typed sphinx-mounts warning.

    The warning type is ``mounts.<topic>`` — for ``topic``
    ``"docname_conflict"`` that is ``mounts.docname_conflict``. Sphinx < 8
    does not display warning types by default, so the type is appended to
    the message there to keep the console output self-explanatory on all
    supported versions.

    :param logger: The module logger to emit through.
    :param message: The warning text (already including the
        ``sphinx-mounts:`` prefix where appropriate).
    :param topic: One of the registered :data:`WarningTopics`.
    :param location: Optional docname (or ``docname:lineno``) the warning
        belongs to.
    """
    if version_info < (8,):
        message = f"{message} [{WARNING_TYPE}.{topic}]"
    logger.warning(message, type=WARNING_TYPE, subtype=topic, location=location)
