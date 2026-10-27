"""The ``[variants]`` table, with the ``[needs] variant_data*`` fallback.

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
once). Hard failures raise :class:`~ub_project.project.ProjectConfigError`.

A consumer that nests its configuration under a prefix (``[tool.acme.needs]`` in a
``pyproject.toml``, where PEP 518 reserves the top level) passes both tables' paths, and
every diagnostic path and message names the table as the consumer placed it.

A consumer that takes a data file from outside the document -- a command-line override --
passes it as ``data_file_override`` (``NO_DATA_FILE`` for one that names no file). It
names a FILE, not a location: the location, the refusals and the findings are those of
the document as written, and the override only replaces the data file of the location
read, which is then never opened.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ub_project.project import (
    ProjectConfigError,
    anchor,
    render_path,
    select_table,
    table_path,
)
from ub_project.variant_data import (
    deep_merge,
    load_variant_data_file,
    resolve_variant_data,
)

#: The default path of the table this module reads: the top level of the document.
VARIANTS_TABLE = "variants"

#: The keys of ``[variants]``, and their legacy spellings in ``[needs]``, in that order.
VARIANTS_KEYS = ("data", "data_file")
LEGACY_KEYS = ("variant_data", "variant_data_file")

#: Diagnostic codes. Fixed: consumers suppress and test against them. They are the BARE
#: subcodes; ubCode is to carry them under its own ``config.`` prefix
#: (``config.variant_data_location``), and the conformance corpus compares the bare form.
VARIANT_DATA_LOCATION = "variant_data_location"
VARIANT_DATA_LEGACY_LOCATION = "variant_data_legacy_location"
VARIANTS_UNKNOWN_KEY = "variants_unknown_key"


class NoDataFile(enum.Enum):
    """The type of :data:`NO_DATA_FILE`, a sentinel with one value."""

    NO_DATA_FILE = "NO_DATA_FILE"

    def __repr__(self) -> str:
        return "ub_project.NO_DATA_FILE"


#: The data-file override that names NO file (reading contract, section 6.8): the data
#: file of the location read is replaced by none -- not opened, not validated -- and the
#: location's inline table is the whole map. sphinx-needs passes it for
#: ``-D needs_variant_data_file=``, the command line's "no data file".
NO_DATA_FILE = NoDataFile.NO_DATA_FILE

Severity = Literal["warning", "info"]
Location = Literal["variants", "needs"]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A non-fatal finding, returned for the consumer to report -- or not.

    ``code``, ``path`` and ``message`` are those of ubCode's ``ConfigResolutionDiagnostic``
    (whose ``code``, where it has one, carries a ``config.`` prefix), so that the conformance corpus can compare
    the two readers' findings by ``code`` and ``path``; ``severity`` is this package's.
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
    """The data file read: the override when there is one, as it was passed (``None``
    for :data:`NO_DATA_FILE`); otherwise the data file of the location read, anchored at
    the TOML's directory."""
    location: Location | None
    """The table the data came from, or ``None`` when neither declared any and there is
    no override (with an override and neither declared, ``"variants"``)."""
    diagnostics: tuple[Diagnostic, ...]
    """Every non-fatal finding, in a stable order."""


def read_variants(
    root_table: Mapping[str, object],
    toml_path: Path,
    *,
    needs_table: str | Sequence[str] = "needs",
    variants_table: str | Sequence[str] = VARIANTS_TABLE,
    data_file_override: Path | NoDataFile | None = None,
) -> VariantsResult:
    """Read the project's variant data from ``[variants]``, or from the legacy location.

    :param root_table: The parsed TOML document.
    :param toml_path: The file *root_table* came from. Relative ``data_file`` values are
        anchored at its directory, and error messages name it.
    :param needs_table: Where the legacy keys live inside *root_table*, dotted or as a
        sequence of keys -- ``"tool.acme.needs"`` for a project that nests its sphinx-needs
        configuration under a prefix.
    :param variants_table: Where ``[variants]`` lives inside *root_table*, in the same
        forms -- ``"tool.acme.variants"`` beside a prefixed *needs_table*. A ``variants``
        table anywhere else is not read, and not reported.
    :param data_file_override: A data file from outside the document,
        :data:`NO_DATA_FILE` for an override that names no file, or ``None`` for no
        override. It replaces the data file of the location read without that file being
        opened, and the location's inline table is still merged over it; it never decides
        the location -- with neither declared, it is read as ``[variants]`` with no inline
        table. It is used as given: anchoring a relative override is the consumer's
        (its own route's rule), never the TOML's directory.
    :raises ProjectConfigError: If a table or key has the wrong type, if the inline data is
        malformed, or if the data file read -- the override, or else the location's -- is
        missing or malformed. An error in the override's file is the file's own message,
        not prefixed with the TOML file and table, which did not name it.
    """
    needs_path = table_path(needs_table)
    needs_dotted = render_path(needs_path)
    variants_path = table_path(variants_table)
    variants_dotted = render_path(variants_path)

    diagnostics: list[Diagnostic] = []
    # an error, not something to skip, when `variants` is not a table: the name is this
    # contract's, and a `variants = "..."` read as "no variant data" would be the silent
    # vanishing the table exists to end
    variants = select_table(root_table, variants_path, source=toml_path) or {}
    for key in sorted(set(variants) - set(VARIANTS_KEYS)):
        diagnostics.append(
            Diagnostic(
                code=VARIANTS_UNKNOWN_KEY,
                path=render_path((*variants_path, key)),
                message=(
                    f"{toml_path}: ignoring unknown key {key!r} in [{variants_dotted}]; "
                    f"this version reads {' and '.join(VARIANTS_KEYS)}"
                ),
                severity="warning",
            )
        )
    needs = select_table(root_table, needs_path, source=toml_path) or {}
    # "declared" is "set to a value": TOML has no null, and a Python caller's `None` means
    # absent everywhere else in this package (`select_table` included)
    declared_legacy = [key for key in LEGACY_KEYS if needs.get(key) is not None]

    if any(variants.get(key) is not None for key in VARIANTS_KEYS):
        location: Location = "variants"
        table, keys, where = variants, VARIANTS_KEYS, f"[{variants_dotted}]"
        for key in declared_legacy:
            diagnostics.append(
                Diagnostic(
                    code=VARIANT_DATA_LOCATION,
                    path=f"{needs_dotted}.{key}",
                    message=(
                        f"{toml_path}: [{needs_dotted}] {key} is ignored because "
                        f"[{variants_dotted}] is set, and only one location is read; "
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
                        f"[{needs_dotted}] {key}; [{variants_dotted}] {current} is the "
                        "current one"
                    ),
                    severity="info",
                )
            )
    elif data_file_override is not None:
        # neither declares: the override is read as [variants] with no inline table
        location = "variants"
        table, keys, where = {}, VARIANTS_KEYS, f"[{variants_dotted}]"
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
        raise ProjectConfigError(msg)
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
            raise ProjectConfigError(msg)
        data_file = anchor(file_value, toml_path.parent)
    base: dict[str, Any] = {}
    if data_file_override is NO_DATA_FILE:
        # replaced by none: the value was held to its type above, its file never opened
        data_file = None
    elif data_file_override is not None:
        # the value it replaces was held to its type above, and its file is never opened
        data_file = data_file_override
        base = load_variant_data_file(data_file_override)
    try:
        if data_file_override is None:
            data = resolve_variant_data(inline, data_file)
        else:
            data = deep_merge(base, resolve_variant_data(inline, None))
    except ProjectConfigError as error:
        msg = f"{toml_path}: {where}: {error}"
        raise ProjectConfigError(msg) from error
    return VariantsResult(
        data=data,
        data_file=data_file,
        location=location,
        diagnostics=tuple(diagnostics),
    )
