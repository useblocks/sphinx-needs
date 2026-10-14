"""The needs exchange file (``needs.json``): reading its envelope.

A needs exchange file holds one or more *versions* of a project's needs::

    {"current_version": "1.0", "versions": {"1.0": {"needs": {"<id>": {...}}, ...}}}

This module reads that envelope, selects a version, and hands out the version's need
records. It is standard library only and knows nothing of the project that reads the
file: it does not log, it does not know which fields a project defines, and it decides
no policy. What it finds is returned as :class:`Diagnostic` values -- a code, the
dotted JSON path of what was found, and a message -- for the reader to report as it
sees fit; a file no record can be read from raises :class:`ExchangeError`.

The rules it reads by are written once, in the package's contract,
``design/exchange-contract.md``: the envelope and its ``format_version`` (section 3),
selecting a version (4), a record -- the key is its id, the legacy ``description`` --
(6), the schema defaults (7), every code (8), and the file's ids as its namespace, which
a reader that prefixes them follows (11). The corpus
``tests/fixtures/needs_json_reading_conformance.toml`` pins them.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = (
    "CURRENT_VERSION_MISSING",
    "DEFAULTS_REMOVED_WITHOUT_SCHEMA",
    "FORMAT_VERSION",
    "FORMAT_VERSION_INVALID",
    "FORMAT_VERSION_UNSUPPORTED",
    "ID_MISMATCH",
    "INVALID_JSON",
    "NEEDS_MISSING",
    "NOT_AN_OBJECT",
    "RECORD_NOT_OBJECT",
    "VERSIONS_MISSING",
    "VERSION_NOT_FOUND",
    "Diagnostic",
    "Document",
    "ExchangeError",
    "Record",
    "Version",
    "load",
    "map_legacy_keys",
    "parse",
)

FORMAT_VERSION = 1
"""The format version this reader reads; a file with no ``format_version`` is of it."""

# the codes of an ExchangeError: no record can be read from the source
INVALID_JSON = "invalid_json"
"""The file cannot be read, is not UTF-8, or is not valid JSON."""
NOT_AN_OBJECT = "not_an_object"
"""The top level is not a JSON object."""
FORMAT_VERSION_INVALID = "format_version_invalid"
"""``format_version`` is present, and is not an integer of 1 or more."""
VERSIONS_MISSING = "versions_missing"
"""``versions`` is absent or not an object."""
CURRENT_VERSION_MISSING = "current_version_missing"
"""No version is requested, and ``current_version`` is absent, not a string, or empty
(and the file has no version of that empty name)."""
VERSION_NOT_FOUND = "version_not_found"
"""The version asked for (requested, or the current one) is not a key of ``versions``."""
NEEDS_MISSING = "needs_missing"
"""The selected version has no ``needs`` object."""

# the codes of a Diagnostic: the source is read, and this is reported
RECORD_NOT_OBJECT = "record_not_object"
"""A value of ``needs`` is not an object; that record is skipped."""
ID_MISMATCH = "id_mismatch"
"""A record's ``id`` differs from its key; the key is its id."""
FORMAT_VERSION_UNSUPPORTED = "format_version_unsupported"
"""``format_version`` is above :data:`FORMAT_VERSION`; the file is read as that format."""
DEFAULTS_REMOVED_WITHOUT_SCHEMA = "defaults_removed_without_schema"
"""The version was written without its default values, and carries no ``needs_schema``
to restore them from."""


class ExchangeError(Exception):
    """A needs exchange file no record can be read from.

    :param code: What is wrong, one of the module's error codes.
    :param message: What is wrong, for a person.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Something found in a file that is read nonetheless."""

    code: str
    """What was found, one of the module's diagnostic codes."""
    path: str
    """The dotted JSON path of what was found, e.g. ``versions.1.0.needs.REQ_1.id``."""
    message: str
    """What was found, for a person."""


@dataclass(frozen=True, slots=True)
class Record:
    """One need record of a version."""

    key: str
    """The key of the record in the version's ``needs``: the need's id."""
    fields: dict[str, Any]
    """The record's fields, its ``id`` the key; the reader's own copy."""
    diagnostics: tuple[Diagnostic, ...] = ()
    """What was found in this record."""


@dataclass(frozen=True, slots=True)
class Version:
    """A selected version of a document."""

    name: str
    """The version's key in ``versions``."""
    data: Mapping[str, Any]
    """The version's object, as the file has it."""
    diagnostics: tuple[Diagnostic, ...] = field(default=())
    """What was found in the version, beside its records: the records skipped, and
    stripped defaults with no schema to restore them."""

    def schema_defaults(self) -> dict[str, Any]:
        """The ``default`` of each property of the version's ``needs_schema``."""
        schema = self.data.get("needs_schema")
        properties = schema.get("properties") if isinstance(schema, Mapping) else None
        if not isinstance(properties, Mapping):
            return {}
        return {
            name: spec["default"]
            for name, spec in properties.items()
            if isinstance(spec, Mapping) and "default" in spec
        }

    def records(self, apply_schema_defaults: bool = True) -> list[Record]:
        """The version's records, in the file's order.

        The key of each is its id, its legacy keys are mapped, and the schema defaults
        are merged under it (contract sections 6 and 7). A value of ``needs`` that is
        not an object is not a record (it is reported in :attr:`diagnostics`). Each
        record's ``fields`` is a new dict, but its values are not copied: a list or
        object value is the document's own, and a default is the same object in every
        record it fills. A reader replaces a value rather than changing it in place.
        (Copying them costs more than reading the file: about a second for a needs.json
        of twenty thousand needs.)

        :param apply_schema_defaults: Merge the ``needs_schema`` defaults under each
            record.
        """
        defaults = self.schema_defaults() if apply_schema_defaults else {}
        needs: Mapping[str, Any] = self.data["needs"]
        result: list[Record] = []
        for key, value in needs.items():
            if not isinstance(value, Mapping):
                continue
            fields = {**defaults, **value}
            diagnostics: list[Diagnostic] = []
            if "id" in value and value["id"] != key:
                diagnostics.append(
                    Diagnostic(
                        ID_MISMATCH,
                        _path("versions", self.name, "needs", key, "id"),
                        f"the need keyed {key!r} has the id {value['id']!r}; "
                        "the key is its id",
                    )
                )
            fields["id"] = key
            map_legacy_keys(fields)
            result.append(Record(key, fields, tuple(diagnostics)))
        return result


@dataclass(frozen=True, slots=True)
class Document:
    """A parsed needs exchange file."""

    data: Mapping[str, Any]
    """The top-level object, as the file has it."""

    def select_version(self, requested: str | None) -> Version:
        """The version ``requested``, or the file's ``current_version`` (contract
        sections 3 and 4).

        :raises ExchangeError: If ``format_version`` is not an integer of 1 or more,
            ``versions`` is missing, no version is requested and ``current_version``
            names none, the version is not in the file, or it has no ``needs`` object.
        """
        diagnostics: list[Diagnostic] = []
        if "format_version" in self.data:
            stated = self.data["format_version"]
            # a JSON ``true`` is a Python ``bool``, which is an ``int``: not a version
            if isinstance(stated, bool) or not isinstance(stated, int) or stated < 1:
                raise ExchangeError(
                    FORMAT_VERSION_INVALID,
                    f"'format_version' is {stated!r}, not an integer of 1 or more",
                )
            if stated > FORMAT_VERSION:
                diagnostics.append(
                    Diagnostic(
                        FORMAT_VERSION_UNSUPPORTED,
                        _path("format_version"),
                        f"the file is of format version {stated}; this reader reads "
                        f"format version {FORMAT_VERSION}, and reads the file as that",
                    )
                )
        versions = self.data.get("versions")
        if not isinstance(versions, Mapping):
            raise ExchangeError(
                VERSIONS_MISSING, "'versions' is missing or not an object"
            )
        if requested is None:
            current = self.data.get("current_version")
            # an empty name is a version's name when the file has one by it: the
            # writer names the version after the project's ``version``, which may be
            # unset
            if not isinstance(current, str) or not (current or current in versions):
                raise ExchangeError(
                    CURRENT_VERSION_MISSING,
                    "no version is requested and 'current_version' is missing, "
                    "empty or not a string",
                )
            requested = current
        if requested not in versions:
            raise ExchangeError(
                VERSION_NOT_FOUND,
                f"Version {requested!r} not found in the file: {list(versions)}",
            )
        data = versions[requested]
        if not isinstance(data, Mapping) or not isinstance(data.get("needs"), Mapping):
            raise ExchangeError(
                NEEDS_MISSING, f"Version {requested} has no 'needs' object"
            )
        diagnostics.extend(
            Diagnostic(
                RECORD_NOT_OBJECT,
                _path("versions", requested, "needs", key),
                f"the need {key!r} is not an object; it is skipped",
            )
            for key, value in data["needs"].items()
            if not isinstance(value, Mapping)
        )
        if data.get("needs_defaults_removed") is True and "needs_schema" not in data:
            diagnostics.append(
                Diagnostic(
                    DEFAULTS_REMOVED_WITHOUT_SCHEMA,
                    _path("versions", requested, "needs_defaults_removed"),
                    f"Version {requested} was written without its default values "
                    "('needs_defaults_removed') and has no 'needs_schema' to restore "
                    "them from; the reading project's defaults are used",
                )
            )
        return Version(requested, data, tuple(diagnostics))


def parse(text: str | bytes) -> Document:
    """Parse a needs exchange file's text (``bytes`` are decoded as UTF-8).

    :raises ExchangeError: If it is not UTF-8, not JSON, or not a JSON object.
    """
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError as err:
            raise ExchangeError(INVALID_JSON, f"not valid UTF-8: {err}") from err
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:
        raise ExchangeError(INVALID_JSON, f"not valid JSON: {err}") from err
    if not isinstance(data, dict):
        raise ExchangeError(NOT_AN_OBJECT, "the top level is not a JSON object")
    return Document(data)


def load(path: str | Path) -> Document:
    """Read and parse a needs exchange file (UTF-8).

    :raises ExchangeError: If the file cannot be read, or :func:`parse` refuses it.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as err:
        raise ExchangeError(INVALID_JSON, f"not valid UTF-8: {err}") from err
    except OSError as err:
        raise ExchangeError(INVALID_JSON, f"cannot be read: {err}") from err
    return parse(text)


def map_legacy_keys(fields: dict[str, Any]) -> None:
    """Rename a record's legacy keys in place: a ``description`` is the ``content``
    when that is absent or empty (sphinx-needs before 4.0 wrote ``description``;
    contract section 6.3)."""
    if "description" in fields and not fields.get("content"):
        fields["content"] = fields.pop("description")


def _path(*parts: str) -> str:
    return ".".join(parts)
