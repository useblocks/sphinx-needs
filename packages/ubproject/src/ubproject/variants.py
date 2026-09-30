"""The top-level ``[variants]`` table, with the ``[needs] variant_data*`` fallback.

``[variants]`` holds the project's variant data for every tool that reads it::

    [variants]
    data_file = "variants.json"   # ONE path, a string, anchored at this file's directory
    [variants.data]               # deep-merged over the file; the inline table wins
    edition = "pro"

Before it existed the same two values lived in the ``[needs]`` table, as
``variant_data_file`` and ``variant_data``, and every reader still accepts them there.
Which location is read is decided WHOLE: both keys come from one table, never one from
each.

========================================  =================================================
declared                                  read
========================================  =================================================
``[variants]`` only                       ``[variants]``
``[needs] variant_data*`` only            ``[needs]``, plus ``variant_data_legacy_location``
both                                      ``[variants]``, plus ``variant_data_location``
                                          for every ``[needs]`` key it ignores
neither                                   nothing: an empty map
========================================  =================================================

A location is DECLARED when it holds at least one of its two keys. A ``[variants]`` table
holding neither -- empty, or only keys this version does not know -- declares nothing, so
it cannot switch a project's ``[needs]`` data off.

Diagnostics are RETURNED, never logged, and the package takes no side on them: whether
the legacy location deserves a warning is the consumer's policy (sphinx-needs will warn,
to move users; ubCode will not, because it supports several sphinx-needs versions at
once). Hard failures raise :class:`~ubproject.project.UbprojectError`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ubproject.project import UbprojectError, anchor, select_table, table_path
from ubproject.variant_data import resolve_variant_data

#: The top-level table this module reads.
VARIANTS_TABLE = "variants"

#: The keys of ``[variants]``, and their legacy spellings in ``[needs]``, in that order.
VARIANTS_KEYS = ("data", "data_file")
LEGACY_KEYS = ("variant_data", "variant_data_file")

#: Diagnostic codes. Fixed: consumers suppress and test against them, and ubCode's
#: diagnostics carry the same strings.
VARIANT_DATA_LOCATION = "variant_data_location"
VARIANT_DATA_LEGACY_LOCATION = "variant_data_legacy_location"
VARIANTS_UNKNOWN_KEY = "variants_unknown_key"

Severity = Literal["warning", "info"]
Location = Literal["variants", "needs"]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A non-fatal finding, returned for the consumer to report -- or not.

    The fields are those of ubCode's ``ConfigResolutionDiagnostic``, so that the
    conformance corpus can compare the two readers' findings by ``code`` and ``path``.
    """

    code: str
    """One of the fixed codes above."""
    path: str
    """The dotted TOML path the finding is about, e.g. ``needs.variant_data_file``."""
    message: str
    """A sentence for a human; its wording is not part of any contract."""
    severity: Severity
    """``"warning"`` for something the file should change, ``"info"`` otherwise."""


@dataclass(frozen=True, slots=True)
class VariantsResult:
    """What :func:`read_variants` found."""

    data: dict[str, Any]
    """The merged variant map: the file, with the inline table deep-merged on top."""
    data_file: Path | None
    """The data file of the location read, anchored at the TOML's directory."""
    location: Location | None
    """The table the data came from, or ``None`` when neither declared any."""
    diagnostics: tuple[Diagnostic, ...]
    """Every non-fatal finding, in a stable order."""


def read_variants(
    root_table: Mapping[str, object],
    toml_path: Path,
    *,
    needs_table: str | Sequence[str] = "needs",
) -> VariantsResult:
    """Read the project's variant data from ``[variants]``, or from the legacy location.

    :param root_table: The parsed TOML document (or the table a consumer's prefix
        selected): ``[variants]`` is read from its top level.
    :param toml_path: The file *root_table* came from. Relative ``data_file`` values are
        anchored at its directory, and error messages name it.
    :param needs_table: Where the legacy keys live inside *root_table*, dotted or as a
        sequence of keys -- ``"tool.acme.needs"`` for a project that nests its sphinx-needs
        configuration under a prefix.
    :raises UbprojectError: If a table or key has the wrong type, if the inline data is
        malformed, or if the data file of the location read is missing or malformed.
    """
    needs_path = table_path(needs_table)
    needs_dotted = ".".join(needs_path)

    diagnostics: list[Diagnostic] = []
    # an error, not something to skip, when `variants` is not a table: the name is this
    # contract's, and a `variants = "..."` read as "no variant data" would be the silent
    # vanishing the table exists to end
    variants = select_table(root_table, VARIANTS_TABLE, source=toml_path) or {}
    for key in sorted(set(variants) - set(VARIANTS_KEYS)):
        diagnostics.append(
            Diagnostic(
                code=VARIANTS_UNKNOWN_KEY,
                path=f"{VARIANTS_TABLE}.{key}",
                message=(
                    f"{toml_path}: ignoring unknown key {key!r} in [{VARIANTS_TABLE}]; "
                    f"this version reads {' and '.join(VARIANTS_KEYS)}"
                ),
                severity="warning",
            )
        )
    needs = select_table(root_table, needs_path, source=toml_path) or {}
    declared_legacy = [key for key in LEGACY_KEYS if key in needs]

    if any(key in variants for key in VARIANTS_KEYS):
        location: Location = "variants"
        table, keys, where = variants, VARIANTS_KEYS, f"[{VARIANTS_TABLE}]"
        for key in declared_legacy:
            diagnostics.append(
                Diagnostic(
                    code=VARIANT_DATA_LOCATION,
                    path=f"{needs_dotted}.{key}",
                    message=(
                        f"{toml_path}: [{needs_dotted}] {key} is ignored because "
                        f"[{VARIANTS_TABLE}] is set, and only one location is read; "
                        f"remove the [{needs_dotted}] key"
                    ),
                    severity="warning",
                )
            )
    elif declared_legacy:
        location = "needs"
        table, keys, where = needs, LEGACY_KEYS, f"[{needs_dotted}]"
        for key in declared_legacy:
            current = VARIANTS_KEYS[LEGACY_KEYS.index(key)]
            diagnostics.append(
                Diagnostic(
                    code=VARIANT_DATA_LEGACY_LOCATION,
                    path=f"{needs_dotted}.{key}",
                    message=(
                        f"{toml_path}: variant data is read from its legacy location "
                        f"[{needs_dotted}] {key}; [{VARIANTS_TABLE}] {current} is the "
                        "current one"
                    ),
                    severity="info",
                )
            )
    else:
        return VariantsResult(
            data={}, data_file=None, location=None, diagnostics=tuple(diagnostics)
        )

    inline_key, file_key = keys
    inline = table.get(inline_key)
    if inline is not None and not isinstance(inline, dict):
        msg = (
            f"{toml_path}: {where} {inline_key} must be a table, "
            f"got {type(inline).__name__}"
        )
        raise UbprojectError(msg)
    file_value = table.get(file_key)
    data_file: Path | None = None
    if file_value is not None:
        if not isinstance(file_value, str) or not file_value:
            got = (
                repr(file_value)
                if isinstance(file_value, str)
                else type(file_value).__name__
            )
            msg = (
                f"{toml_path}: {where} {file_key} must be one non-empty path string, "
                f"got {got}"
            )
            raise UbprojectError(msg)
        data_file = anchor(file_value, toml_path.parent)
    try:
        data = resolve_variant_data(inline, data_file)
    except UbprojectError as error:
        msg = f"{toml_path}: {where}: {error}"
        raise UbprojectError(msg) from error
    return VariantsResult(
        data=data,
        data_file=data_file,
        location=location,
        diagnostics=tuple(diagnostics),
    )
