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

On opt-in, it also reads a DRAFT of the next format, ``"2a1"`` (``select_version(...,
drafts=("2a1",))``): an experimental format, which may change or be removed in any
release while it is a draft. Its rules are ``design/v2a1-draft.md``, and its own corpus
``tests/fixtures/needs_json_2a1_draft_conformance.toml``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = (
    "CONTENT_NOT_OBJECT",
    "CURRENT_VERSION_MISSING",
    "DEFAULTS_REMOVED_WITHOUT_SCHEMA",
    "DRAFT_HAS_VERSIONS",
    "DUPLICATE_ID",
    "FIELDS_NOT_OBJECT",
    "FIELD_RESERVED",
    "FORMAT_VERSION",
    "FORMAT_VERSION_INVALID",
    "FORMAT_VERSION_UNSUPPORTED",
    "HOP_INVALID",
    "ID_MISMATCH",
    "ID_MISSING",
    "ID_NOT_STRING",
    "INVALID_JSON",
    "LINKS_NOT_OBJECT",
    "LINK_INVALID",
    "NEEDS_MISSING",
    "NOT_AN_OBJECT",
    "PROJECT_INVALID",
    "RECORD_NOT_OBJECT",
    "SOURCE_NOT_A_LIST",
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

#: A pre-release of a format, as a later writer spells its ``format_version``:
#: ``"2a1"``, ``"2b1"``, ``"2rc1"`` (PEP 440's normalised pre-release segments).
_PRE_RELEASE = re.compile(r"[1-9][0-9]*(?:a|b|rc)[1-9][0-9]*")

# the codes of an ExchangeError: no record can be read from the source
INVALID_JSON = "invalid_json"
"""The file cannot be read, is not UTF-8, or is not valid JSON."""
NOT_AN_OBJECT = "not_an_object"
"""The top level is not a JSON object."""
FORMAT_VERSION_INVALID = "format_version_invalid"
"""``format_version`` is present, and is neither an integer of 1 or more nor a
pre-release string such as ``"2a1"``."""
FORMAT_VERSION_UNSUPPORTED = "format_version_unsupported"
"""``format_version`` names a format this reader does not read: an integer above
:data:`FORMAT_VERSION`, or a pre-release string such as ``"2a1"``."""
VERSIONS_MISSING = "versions_missing"
"""``versions`` is absent or not an object."""
CURRENT_VERSION_MISSING = "current_version_missing"
"""No version is requested, and ``current_version`` is absent, not a string, or empty
(and the file has no version of that empty name)."""
VERSION_NOT_FOUND = "version_not_found"
"""The version asked for (requested, or the current one) is not a key of ``versions``."""
NEEDS_MISSING = "needs_missing"
"""The selected version has no ``needs`` object; in a ``"2a1"`` draft, the document's
``needs`` is absent or not an array."""
DRAFT_HAS_VERSIONS = "draft_has_versions"
"""A ``"2a1"`` draft has a ``versions`` or a ``current_version`` key: a draft has none,
and a reader of format 1 that does not check ``format_version`` would read one that kept
them as format 1."""

# the codes of a Diagnostic: the source is read, and this is reported
RECORD_NOT_OBJECT = "record_not_object"
"""A value of ``needs`` is not an object; that record is skipped."""
ID_MISMATCH = "id_mismatch"
"""A record's ``id`` differs from its key; the key is its id."""
DEFAULTS_REMOVED_WITHOUT_SCHEMA = "defaults_removed_without_schema"
"""The version was written without its default values, and carries no ``needs_schema``
to restore them from."""

# the codes of a Diagnostic of a ``"2a1"`` draft (``design/v2a1-draft.md``), besides
# ``record_not_object``
PROJECT_INVALID = "project_invalid"
"""The draft's ``project`` is absent or not an object, or its ``name`` or ``version`` is
not a string; it is read as absent."""
ID_MISSING = "id_missing"
"""A draft's record has no ``id``; it is skipped."""
ID_NOT_STRING = "id_not_string"
"""A draft's record has an ``id`` that is not a string; it is skipped."""
DUPLICATE_ID = "duplicate_id"
"""A draft's record has the ``id`` of an earlier one; the first is read, this one
skipped."""
FIELDS_NOT_OBJECT = "fields_not_object"
"""A draft's record has a ``fields`` that is not an object; its fields are not read."""
FIELD_RESERVED = "field_reserved"
"""A key of a draft's record's ``fields`` is one the projection owns (``id``, ``type``,
``content``, ``doctype``, ``parts``, ``docname``, ``sections``, ``section_name``,
``signature``); it is not read."""
LINKS_NOT_OBJECT = "links_not_object"
"""A draft's record has a ``links`` that is not an object; its links are not read."""
LINK_INVALID = "link_invalid"
"""A link type's value is not an array, or one of its entries is neither a string nor an
object of a string ``id`` (and a string ``part`` and ``condition``, if given); that link
type, or that entry, is not read."""
CONTENT_NOT_OBJECT = "content_not_object"
"""A draft's record has a ``content`` that is not an object; its content is not read."""
SOURCE_NOT_A_LIST = "source_not_a_list"
"""A draft's record has a ``source`` that is not an array; its source is not read."""
HOP_INVALID = "hop_invalid"
"""A hop of a draft's ``source`` is not an object, has no string ``kind``, or has a known
key of the wrong type; that hop is not read."""

#: The drafts of a later format this reader reads, each only when asked to.
_DRAFTS = frozenset({"2a1"})

#: The keys of a draft's projected record that come from the record itself, its
#: ``content`` or its placement, and never from its ``fields``.
_RESERVED_FIELDS = frozenset(
    {
        "id",
        "type",
        "content",
        "doctype",
        "parts",
        "docname",
        "sections",
        "section_name",
        "signature",
    }
)


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
    source: tuple[Mapping[str, Any], ...] = ()
    """The record's hops, innermost first, each as the file has it (the document's own
    object): a ``"2a1"`` draft's ``source``, less any hop that is not valid. Empty for
    a record of format 1, which has none. Experimental, as the draft is."""


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
    format_version: int | str = FORMAT_VERSION
    """The format the version is read as: :data:`FORMAT_VERSION`, or a draft such as
    ``"2a1"``, whose :attr:`data` is the whole document (it has no ``versions``)."""

    def schema_defaults(self) -> dict[str, Any]:
        """The ``default`` of each property of the version's ``needs_schema``; none for a
        ``"2a1"`` draft, which carries no schema."""
        if self.format_version != FORMAT_VERSION:
            return {}
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

        A ``"2a1"`` draft's records are projected to the shape a format-1 record has,
        and carry their hops in :attr:`Record.source` (``design/v2a1-draft.md``); it has
        no schema and no legacy keys, so ``apply_schema_defaults`` changes nothing there.

        :param apply_schema_defaults: Merge the ``needs_schema`` defaults under each
            record. Without them, the legacy keys are still mapped as on the merged
            record: where the schema gives ``content`` a default, every record has a
            ``content`` once merged, so none has its ``description`` renamed.
        """
        if self.format_version != FORMAT_VERSION:
            return _draft_records(self.data["needs"])
        all_defaults = self.schema_defaults()
        defaults = all_defaults if apply_schema_defaults else {}
        # the mapping reads the record as the merge gives it (contract section 6.3)
        maps_legacy_keys = apply_schema_defaults or "content" not in all_defaults
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
            if maps_legacy_keys:
                map_legacy_keys(fields)
            result.append(Record(key, fields, tuple(diagnostics)))
        return result


@dataclass(frozen=True, slots=True)
class Document:
    """A parsed needs exchange file."""

    data: Mapping[str, Any]
    """The top-level object, as the file has it."""

    def select_version(
        self, requested: str | None, *, drafts: Collection[str] = ()
    ) -> Version:
        """The version ``requested``, or the file's ``current_version`` (contract
        sections 3 and 4).

        :param drafts: The drafts of a later format to read as well, of which there is
            one, ``"2a1"`` (``design/v2a1-draft.md``). Without it, a ``"2a1"`` file is
            refused as any later format is. **Experimental**: a draft, and this
            parameter, may change or be removed in any release while the format is a
            draft. A ``"2a1"`` document has one version, which ``None`` selects, and a
            name asked for selects it only when it is the document's
            ``project.version``.
        :raises ValueError: If ``drafts`` names a draft this reader does not know (a
            string is a collection of its characters, so ``"2a1"`` is one too).
        :raises ExchangeError: If ``format_version`` is not a format version or names
            one other than :data:`FORMAT_VERSION` or a draft asked for, ``versions`` is
            missing, no version is requested and ``current_version`` names none, the
            version is not in the file, or it has no ``needs`` object; for a draft, if
            it has ``versions`` or ``current_version``, the name asked for is not its
            ``project.version``, or its ``needs`` is not an array.
        """
        unknown = set(drafts) - _DRAFTS
        if unknown:
            raise ValueError(
                f"unknown drafts {sorted(unknown)!r}: this reader knows "
                f"{sorted(_DRAFTS)!r}"
            )
        if "format_version" in self.data:
            stated = self.data["format_version"]
            if isinstance(stated, str) and stated in drafts:
                return _select_draft(self.data, requested, stated)
            _check_format_version(stated)
        diagnostics: list[Diagnostic] = []
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


def _select_draft(
    data: Mapping[str, Any], requested: str | None, draft: str
) -> Version:
    """The one version of a ``"2a1"`` draft (``design/v2a1-draft.md`` section 2)."""
    for key in ("versions", "current_version"):
        if key in data:
            raise ExchangeError(
                DRAFT_HAS_VERSIONS,
                f"the file is of format version {json.dumps(draft)}, which has no "
                f"{key!r}; a file that has one is not read",
            )
    diagnostics: list[Diagnostic] = []
    project = data.get("project")
    stated: dict[str, str] = {}
    if not isinstance(project, Mapping):
        diagnostics.append(
            Diagnostic(
                PROJECT_INVALID,
                "project",
                "'project' is missing or not an object; the project's name and "
                "version are read as absent",
            )
        )
    else:
        for key in ("name", "version"):
            value = project.get(key)
            if isinstance(value, str):
                stated[key] = value
            elif key in project:
                diagnostics.append(
                    Diagnostic(
                        PROJECT_INVALID,
                        _path("project", key),
                        f"the project's {key!r} is not a string; it is read as absent",
                    )
                )
    version = stated.get("version")
    if requested is not None and requested != version:
        raise ExchangeError(
            VERSION_NOT_FOUND,
            f"Version {requested!r} not found in the file: "
            f"{[] if version is None else [version]}",
        )
    needs = data.get("needs")
    if not isinstance(needs, list):
        raise ExchangeError(NEEDS_MISSING, "'needs' is missing or not an array")
    diagnostics.extend(_draft_kept(needs)[1])
    return Version(version or "", data, tuple(diagnostics), draft)


def _draft_kept(
    needs: list[Any],
) -> tuple[list[tuple[int, str, Mapping[str, Any]]], list[Diagnostic]]:
    """The records of a draft that are read, each with its index, and a finding for each
    that is skipped (``design/v2a1-draft.md`` section 3.1)."""
    kept: list[tuple[int, str, Mapping[str, Any]]] = []
    skipped: list[Diagnostic] = []
    seen: dict[str, int] = {}
    for index, value in enumerate(needs):
        where = _path("needs", str(index))
        if not isinstance(value, Mapping):
            skipped.append(
                Diagnostic(
                    RECORD_NOT_OBJECT,
                    where,
                    f"the need at index {index} is not an object; it is skipped",
                )
            )
        elif "id" not in value:
            skipped.append(
                Diagnostic(
                    ID_MISSING,
                    where,
                    f"the need at index {index} has no 'id'; it is skipped",
                )
            )
        elif not isinstance(need_id := value["id"], str):
            skipped.append(
                Diagnostic(
                    ID_NOT_STRING,
                    _path(where, "id"),
                    f"the need at index {index} has an 'id' that is not a string; "
                    "it is skipped",
                )
            )
        elif need_id in seen:
            skipped.append(
                Diagnostic(
                    DUPLICATE_ID,
                    _path(where, "id"),
                    f"the need at index {index} has the id {need_id!r} of the need at "
                    f"index {seen[need_id]}; the first is read, this one skipped",
                )
            )
        else:
            seen[need_id] = index
            kept.append((index, need_id, value))
    return kept, skipped


def _draft_records(needs: list[Any]) -> list[Record]:
    """A draft's records, each projected to the shape a format-1 record has
    (``design/v2a1-draft.md`` section 3)."""
    return [
        _draft_record(index, need_id, value)
        for index, need_id, value in _draft_kept(needs)[0]
    ]


def _draft_record(index: int, need_id: str, value: Mapping[str, Any]) -> Record:
    where = _path("needs", str(index))
    diagnostics: list[Diagnostic] = []
    projected: dict[str, Any] = {}
    if "fields" in value:
        if isinstance(value["fields"], Mapping):
            for name, field_value in value["fields"].items():
                if name in _RESERVED_FIELDS:
                    diagnostics.append(
                        Diagnostic(
                            FIELD_RESERVED,
                            _path(where, "fields", name),
                            f"{name!r} is not a field of a record: it is the record's "
                            "own, or projected from its content or source; it is not "
                            "read",
                        )
                    )
                else:
                    projected[name] = field_value
        else:
            diagnostics.append(
                Diagnostic(
                    FIELDS_NOT_OBJECT,
                    _path(where, "fields"),
                    "'fields' is not an object; the need's fields are not read",
                )
            )
    if "links" in value:
        if isinstance(value["links"], Mapping):
            projected.update(_draft_links(value["links"], where, diagnostics))
        else:
            diagnostics.append(
                Diagnostic(
                    LINKS_NOT_OBJECT,
                    _path(where, "links"),
                    "'links' is not an object; the need's links are not read",
                )
            )
    if "content" in value:
        content = value["content"]
        if isinstance(content, Mapping):
            if "text" in content:
                projected["content"] = content["text"]
            if "doctype" in content:
                projected["doctype"] = content["doctype"]
            if "parts" in content:
                parts = content["parts"]
                projected["parts"] = (
                    {
                        part_id: {"id": part_id, "content": text}
                        for part_id, text in parts.items()
                    }
                    if isinstance(parts, Mapping)
                    else parts
                )
        else:
            diagnostics.append(
                Diagnostic(
                    CONTENT_NOT_OBJECT,
                    _path(where, "content"),
                    "'content' is not an object; the need's content is not read",
                )
            )
    hops: tuple[Mapping[str, Any], ...] = ()
    if "source" in value:
        if isinstance(value["source"], list):
            hops = _draft_hops(value["source"], where, diagnostics)
        else:
            diagnostics.append(
                Diagnostic(
                    SOURCE_NOT_A_LIST,
                    _path(where, "source"),
                    "'source' is not an array; the need's source is not read",
                )
            )
    placement = next((hop for hop in reversed(hops) if "document" in hop), None)
    if placement is not None:
        projected.update(_placement_keys(placement))
    if "type" in value:
        projected["type"] = value["type"]
    projected["id"] = need_id
    return Record(need_id, projected, tuple(diagnostics), hops)


def _placement_keys(placement: Mapping[str, Any]) -> dict[str, Any]:
    """The format-1 keys a placement hop gives: ``docname``, and ``sections``,
    ``section_name`` and ``signature`` by sphinx-needs' rule for them (its
    ``project_legacy`` and ``NeedItem``'s ``section_name``): the section entries
    innermost first, the innermost of them or ``None``, and the ``signature`` extra of
    the innermost entry of another kind that has a non-empty one, or ``None``."""
    # outermost first in the hop; innermost first in format 1's ``sections``
    inner_first = list(reversed(placement.get("semantic", ())))
    sections = [entry["name"] for entry in inner_first if entry["kind"] == "section"]
    signature = next(
        (
            value
            for entry in inner_first
            if entry["kind"] != "section"
            and (value := entry.get("extras", {}).get("signature"))
        ),
        None,
    )
    return {
        "docname": placement["document"],
        "sections": sections,
        "section_name": sections[0] if sections else None,
        "signature": signature,
    }


def _draft_links(
    links: Mapping[str, Any], where: str, diagnostics: list[Diagnostic]
) -> dict[str, list[Any]]:
    """Each link type's links, as format 1 spells them: ``ID``, ``ID.part``,
    ``ID[condition]`` or ``ID.part[condition]``. A string is handed on as written, so
    the reading project reads it in format 1's grammar too: a ``.`` or ``[`` in it is
    read as a part or a condition there."""
    projected: dict[str, list[Any]] = {}
    for link_type, entries in links.items():
        at = _path(where, "links", link_type)
        if not isinstance(entries, list):
            diagnostics.append(
                Diagnostic(
                    LINK_INVALID,
                    at,
                    f"the links of {link_type!r} are not an array; they are not read",
                )
            )
            continue
        spelled: list[Any] = []
        for position, entry in enumerate(entries):
            if isinstance(entry, str):
                spelled.append(entry)
            elif (
                isinstance(entry, Mapping)
                and isinstance(entry.get("id"), str)
                and all(
                    isinstance(entry[key], str)
                    for key in ("part", "condition")
                    if key in entry
                )
            ):
                spelled.append(
                    _link_string(entry["id"], entry.get("part"), entry.get("condition"))
                )
            else:
                diagnostics.append(
                    Diagnostic(
                        LINK_INVALID,
                        _path(at, str(position)),
                        f"a link of {link_type!r} is neither a string nor an object "
                        "of a string 'id' (and a string 'part' and 'condition'); it is "
                        "not read",
                    )
                )
        projected[link_type] = spelled
    return projected


def _link_string(need_id: str, part: str | None, condition: str | None) -> str:
    """A link as format 1 writes it: sphinx-needs' ``NeedLink.to_link_string``.

    The part follows a ``.`` when it is not empty, and the condition is in brackets one
    deeper than the longest run of ``]`` in it, so that the string reads back as the
    same link.
    """
    base = f"{need_id}.{part}" if part else need_id
    if condition is None:
        return base
    depth = 1 + max((len(run) for run in re.findall(r"\]+", condition)), default=0)
    return f"{base}{'[' * depth}{condition}{']' * depth}"


def _draft_hops(
    source: list[Any], where: str, diagnostics: list[Diagnostic]
) -> tuple[Mapping[str, Any], ...]:
    """The valid hops of a ``source``, each the document's own object."""
    hops: list[Mapping[str, Any]] = []
    for position, hop in enumerate(source):
        problem = _hop_problem(hop)
        if problem is None:
            hops.append(hop)
        else:
            diagnostics.append(
                Diagnostic(
                    HOP_INVALID,
                    _path(where, "source", str(position)),
                    f"the hop at index {position} {problem}; it is not read",
                )
            )
    return tuple(hops)


def _is_line(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _hop_problem(hop: Any) -> str | None:
    """What is wrong with a hop's shape, or ``None`` (``design/v2a1-draft.md``
    section 4). Keys it does not know are not checked."""
    if not isinstance(hop, Mapping):
        return "is not an object"
    if not isinstance(hop.get("kind"), str):
        return "has no string 'kind'"
    for key in ("origin", "document", "language"):
        if key in hop and not isinstance(hop[key], str):
            return f"has a {key!r} that is not a string"
    if "physical" in hop:
        physical = hop["physical"]
        if not isinstance(physical, Mapping):
            return "has a 'physical' that is not an object"
        for key in ("root", "path", "url"):
            if key in physical and not isinstance(physical[key], str):
                return f"has a 'physical.{key}' that is not a string"
        for key in ("start_line", "end_line"):
            if key in physical and not _is_line(physical[key]):
                return f"has a 'physical.{key}' that is not an integer of 1 or more"
        if (
            "start_line" in physical
            and "end_line" in physical
            and physical["end_line"] < physical["start_line"]
        ):
            return "has a 'physical.end_line' before its 'start_line'"
    if "semantic" in hop:
        semantic = hop["semantic"]
        if not isinstance(semantic, list):
            return "has a 'semantic' that is not an array"
        for entry in semantic:
            if not (
                isinstance(entry, Mapping)
                and isinstance(entry.get("kind"), str)
                and isinstance(entry.get("name"), str)
            ):
                return (
                    "has a 'semantic' entry that is not an object of a string "
                    "'kind' and 'name'"
                )
            extras = entry.get("extras", {})
            if not (
                isinstance(extras, Mapping)
                and all(isinstance(text, str) for text in extras.values())
            ):
                return (
                    "has a 'semantic' entry whose 'extras' is not an object of strings"
                )
    return None


def _check_format_version(stated: Any) -> None:
    """Refuse a ``format_version`` that is not :data:`FORMAT_VERSION` (contract
    section 3.1): one that names a later format, or one that is not a format version."""
    # a JSON ``true`` is a Python ``bool``, which is an ``int``: not a version
    integer = isinstance(stated, int) and not isinstance(stated, bool)
    if integer and stated == FORMAT_VERSION:
        return
    # the value as JSON spells it -- ``"2a1"``, ``2``, ``2.0``, ``true``, ``null`` -- and a
    # character outside ASCII as itself, for the person who reads the message; a lone
    # surrogate, which no encoder can write, as its escape
    shown = (
        json.dumps(stated, ensure_ascii=False, default=repr)
        .encode("utf-8", "backslashreplace")
        .decode("utf-8")
    )
    if (integer and stated > FORMAT_VERSION) or (
        isinstance(stated, str) and _PRE_RELEASE.fullmatch(stated) is not None
    ):
        raise ExchangeError(
            FORMAT_VERSION_UNSUPPORTED,
            f"the file is of format version {shown}; this reader reads format "
            f"version {FORMAT_VERSION} only",
        )
    raise ExchangeError(
        FORMAT_VERSION_INVALID,
        f"'format_version' is {shown}, not an integer of 1 or more",
    )


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
    when the record has no ``content`` key at all (sphinx-needs before 4.0 wrote the
    content as ``description`` and, by default, no ``content``; every later writer
    writes ``content``, or its schema default, unless told to leave ``content`` out --
    a file written that way reads as a pre-4.0 one). A record with a ``content`` key,
    whatever its value, keeps its ``description`` (contract section 6.3)."""
    if "description" in fields and "content" not in fields:
        fields["content"] = fields.pop("description")


def _path(*parts: str) -> str:
    return ".".join(parts)
