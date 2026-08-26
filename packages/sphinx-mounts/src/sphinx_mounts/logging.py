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
    "deprecated_confval",
    "deprecated_location",
    "docname_conflict",
    "empty_docname",
    "ignored_option",
    "missing_path",
    "mount_at_occupied",
    "mount_gate_unevaluable",
    "path_escape",
    "toctree_index",
    "unknown_key",
    "unknown_suffix",
    "variant_rule_dropped",
    "variant_rule_unevaluable",
]

#: Codes that name a *hard* failure or an *informational* record rather than a
#: warning, so they never reach :func:`log_warning`. They are listed here
#: because they appear in user-facing message text and users grep for them.
#:
#: ``mounts.variant_data_unreadable``
#:     The variant data file is missing, undecodable, or not a JSON object,
#:     and sphinx-needs is not installed to report it. A hard
#:     ``VariantRuleError``: with no variant map there is no defensible answer
#:     to "which files does this variant contain".
#: ``mounts.variant_root_doc``
#:     A rule that is false for this variant would exclude ``root_doc``. A hard
#:     ``VariantRuleError``, so that Sphinx's own "unable to load the master
#:     document" abort — which blames the source directory for something that
#:     is really an exclusion — is never reachable through a variant rule.
#: ``mounts.variant_glob_dialect``
#:     A rule glob whose spelling has no faithful form for every reader
#:     (``{a,b}``, a ``..`` climb, an absolute path, or ``?`` beside a
#:     separator). A hard ``VariantRuleError`` listing every offender at once.
#: ``mounts.variant_layout``
#:     Rules are declared but the source root they anchor at is not Sphinx's
#:     ``srcdir``, so no rule glob can be expressed as an ``exclude_patterns``
#:     entry. A hard ``VariantRuleError`` naming both directories.
#: ``mounts.variant_excluded_reference``
#:     The downgraded toctree record — INFO, not a warning. See
#:     :mod:`sphinx_mounts.warnings`.
#: ``mounts.mount_gated``
#:     A mount entry's ``if`` is false for this variant, so the whole bundle is
#:     gated off — INFO, not a warning, because gating is what the author asked
#:     for and a warning would fail ``sphinx-build -W`` on a correct build. It
#:     is emitted once per gated mount **whether or not anything references the
#:     bundle**, which is the only signal a large silent absence gets.
NON_WARNING_CODES = (
    "mounts.mount_gated",
    "mounts.variant_data_unreadable",
    "mounts.variant_excluded_reference",
    "mounts.variant_glob_dialect",
    "mounts.variant_layout",
    "mounts.variant_root_doc",
)

#: The INFO record marking one gated-off mount. Named so tests and the
#: extension quote one string; see :data:`NON_WARNING_CODES` for what it means.
MOUNT_GATED_CODE = "mounts.mount_gated"

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
