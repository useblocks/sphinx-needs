"""Turn parsed test reports into a needs.json payload.

Sphinx-free: the conversion runs as a build action, and the documentation build
only imports the result.

Three rules shape the output:

* **Every field is always present.** Absent XML attributes become empty values
  rather than missing keys, and an exported property a case does not carry is
  ``null`` -- the value the build leaves in a registered field a directive did
  not set -- so a schema can simply require a field and a consumer never has
  to distinguish "unset" from "absent".
* **Every field is declared in the file**, in the ``needs_schema`` sphinx-needs
  also writes into the files it produces itself, so the type of a field is
  readable from the artifact instead of only from a Sphinx build with this
  extension loaded. The declarations come from
  :mod:`sphinxcontrib.test_reports.fields`, the same table the extension
  registers its fields from.
* **Nothing depends on the wall clock or on dict ordering**, so the file is a
  cacheable build artifact and a diffable piece of evidence.
"""

import re
import textwrap
from typing import Callable, Iterable, Iterator, Mapping, Sequence, Union

from sphinxcontrib.test_reports.fields import case_needs_schema
from sphinxcontrib.test_reports.identity import (
    UNKNOWN,
    deterministic_case_id,
    split_case_name,
)
from sphinxcontrib.test_reports.projectconfig import DEFAULT_FIELD_NAMES
from sphinxcontrib.test_reports.remote import DEFAULT_URL_PATTERN, source_url

#: A need field value as it appears in needs.json. ``None`` is the value of an
#: exported property the case does not carry, as the build leaves it.
FieldValue = Union[str, list[str], None]
NeedItem = dict[str, FieldValue]

#: A parsed report: the path it was read from, and its top-level suites. The
#: path is what the build's ``test-file``/``test-case`` directives record as
#: the report-path field, so it travels with the suites.
Report = tuple[str, Sequence[Mapping[str, object]]]

#: Version key used when the caller does not supply one. needs.json requires a
#: ``current_version``, but a converted report has no baseline history.
DEFAULT_VERSION = "1.0"

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_WHITESPACE = re.compile(r"\s+")


def flatten_message(message: str) -> str:
    """One-line, ANSI-free rendering of a failure message.

    Used for ``result_text``, which exists to be readable in tables and
    reports; the untruncated detail stays in the need content.
    """
    return _WHITESPACE.sub(" ", _ANSI.sub("", message)).strip()


def _contains(haystack: str, needle: str) -> bool:
    """Whitespace-insensitive containment, for de-duplicating failure text."""
    return _WHITESPACE.sub(" ", needle).strip() in _WHITESPACE.sub(" ", haystack)


def _literal_block(title: str, body: str) -> str:
    """An RST literal block, indented so the need content stays valid.

    The body is dedented as a whole, not line by line: XML pretty-printing adds
    a common indentation that has to go, but a traceback or an assertion diff
    is only readable if its *relative* indentation survives.
    """
    lines = textwrap.dedent(body).strip("\n").split("\n")
    indented = "\n".join(
        f"   {line.rstrip()}" if line.strip() else "" for line in lines
    )
    return f"\n**{title}**::\n\n{indented}\n"


def build_content(case: Mapping[str, object]) -> str:
    """Need content carrying the complete failure evidence.

    googletest reports one ``<failure>`` per failed assertion, each with its own
    message and body, plus captured output -- keeping only the first of them
    loses exactly the detail a reader needs.
    """
    sections: list[str] = []

    parts = _result_parts(case)
    for index, part in enumerate(parts, start=1):
        kind = str(part.get("kind", "result")).capitalize()
        label = f"{kind} {index}" if len(parts) > 1 else kind
        message = str(part.get("message", ""))
        text = str(part.get("text", ""))
        # googletest repeats the body in the message attribute; a second copy
        # is noise, so the message is only shown when it adds something.
        if message and not _contains(text, message):
            sections.append(_literal_block(f"{label} message", message))
        if text:
            sections.append(_literal_block(label, text))

    for key, title in (("system-out", "System-out"), ("system-err", "System-err")):
        captured = str(case.get(key, ""))
        if captured:
            sections.append(_literal_block(title, captured))

    return "".join(sections)


def _result_parts(case: Mapping[str, object]) -> list[Mapping[str, object]]:
    """The case's result parts, as a typed view over the parser's output."""
    raw = case.get("parts")
    if not isinstance(raw, list):
        return []
    return [part for part in raw if isinstance(part, Mapping)]


def _first_message(case: Mapping[str, object]) -> str:
    for part in _result_parts(case):
        message = str(part.get("message", ""))
        if message and message != UNKNOWN:
            return flatten_message(message)
    return ""


def optional(value: object, absent: object) -> str:
    """String form of an attribute, empty when the parser reported it absent."""
    return "" if value is None or value == absent else str(value)


def _mappings(value: object) -> list[Mapping[str, object]]:
    """Typed view over a list of dicts coming from the parser."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def iter_cases(
    suites: Iterable[Mapping[str, object]],
) -> Iterator[tuple[str, Mapping[str, object]]]:
    """Yield ``(suite_name, case)`` pairs, descending into nested suites.

    The parser files the cases of a suite that contains nested ``<testsuite>``
    elements under ``testsuite_nested`` only, so anything that wants to see
    every case of a report has to walk this way -- the export does, and so must
    every diagnostic about the report's cases, or it goes quiet on exactly the
    nested reports Ant and Maven produce.
    """
    for suite in suites:
        name = str(suite.get("name", ""))
        for case in _mappings(suite.get("testcases")):
            yield name, case
        yield from iter_cases(_mappings(suite.get("testsuite_nested")))


def build_need(
    report_path: str,
    suite_name: str,
    case: Mapping[str, object],
    *,
    need_type: str = "testcase",
    tags: Sequence[str] = (),
    link_properties: Mapping[str, str] | None = None,
    base_url: str = "",
    commit: str = "",
    url_pattern: str = DEFAULT_URL_PATTERN,
    fields: Mapping[str, str] | None = None,
    extra_options: Sequence[str] = (),
    collisions: set[str] | None = None,
) -> NeedItem:
    """One test case as a need item, shaped like the build's ``test-case``.

    The field names are those of the directives -- ``suite``/``case``/
    ``case_name``/``case_parameter``/``classname``/``result``/``time`` plus the
    renameable report-path and source-location fields in *fields* (see
    :data:`DEFAULT_FIELD_NAMES`) -- and so are the values: the title is the
    case name and ``result`` keeps the parser's spelling (``failed``, which is
    also a documented field value and the ``tr_failed`` CSS class, see
    :mod:`sphinxcontrib.test_reports.results`), so that a need imported from
    the produced ``needs.json`` and one created locally from the same report
    are indistinguishable to a schema, a filter or a ``needtable``.

    XML properties become fields under their own names only when listed in
    *extra_options* -- the same list that makes the build register them as need
    options and accept them -- so an import never has to drop them as unknown
    keys. Every listed name is written, ``None`` when the case has no such
    property, so the field is there to be required. A property mapped by
    *link_properties* becomes a link field regardless. Everything else is left
    out; :func:`build_needs_file` reports what was left out, once.

    A listed property whose name is already taken by a built-in or link field
    cannot become a field: the built-in value wins -- silently overwriting
    ``result`` or the report path would be worse -- but silently dropping the
    property is not acceptable either, so its name is added to *collisions*
    when the case carries it, for the caller to report once.
    """
    link_properties = link_properties or {}
    names = {**DEFAULT_FIELD_NAMES, **(fields or {})}
    exported = list(dict.fromkeys(extra_options, True))  # deduplicated, in order

    classname = optional(case.get("classname"), UNKNOWN)
    name = optional(case.get("name"), UNKNOWN)
    case_name, case_parameter = split_case_name(name)
    source_file = optional(case.get("file"), UNKNOWN)
    source_line = optional(case.get("line"), -1)
    time = optional(case.get("time"), -1)

    url = source_url(base_url, commit, source_file, source_line, url_pattern)
    content = build_content(case)

    need: NeedItem = {
        "id": deterministic_case_id(
            classname=classname, name=name, file=source_file, prefix=need_type
        ),
        "type": need_type,
        "title": name,
        # ``content``, as sphinx-needs >= 4 writes and reads it. Older versions
        # read the need text from ``description`` only, and current ones flag a
        # file carrying both -- so importing a converted file needs >= 4.
        "content": content,
        "tags": list(tags),
        "suite": suite_name,
        "case": name,
        "case_name": case_name,
        "case_parameter": case_parameter,
        "classname": classname,
        names["file_option"]: report_path,
        names["source_file_option"]: source_file,
        names["source_line_option"]: source_line,
        "time": time,
        "result": str(case.get("result", "")),
        "result_text": _first_message(case),
        # The same URL twice on purpose: external_url drives the external-needs
        # rendering, while a plain field stays usable for needs imported as
        # local needs (via a needs_string_links entry).
        "external_url": url,
        "remote_url": url,
    }

    properties = case.get("properties") or {}
    if not isinstance(properties, Mapping):
        properties = {}

    # Link fields are emitted even when empty, so a schema can require them.
    for property_name, link_field in link_properties.items():
        raw = str(properties.get(property_name, ""))
        need[link_field] = [item.strip() for item in raw.split(",") if item.strip()]

    # Exported properties are emitted for every case too; absent, the field is
    # null, as the build leaves a registered field a directive did not set.
    for property_name in exported:
        if property_name in link_properties:
            continue  # the link field carries it
        if property_name in need:
            if property_name in properties and collisions is not None:
                collisions.add(property_name)
            continue
        value = properties.get(property_name)
        need[property_name] = None if value is None else str(value)

    return need


def build_needs_file(
    reports: Iterable[Report],
    *,
    project: str = "",
    version: str = DEFAULT_VERSION,
    need_type: str = "testcase",
    tags: Sequence[str] = (),
    link_properties: Mapping[str, str] | None = None,
    base_url: str = "",
    commit: str = "",
    url_pattern: str = DEFAULT_URL_PATTERN,
    fields: Mapping[str, str] | None = None,
    extra_options: Sequence[str] = (),
    warn: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """The complete needs.json payload for a set of parsed reports.

    No ``created`` key is written: a wall clock inside a cacheable build output
    would change the file on every run.

    Properties that are neither in *extra_options* nor mapped by
    *link_properties* are not exported (see :func:`build_need`); their names are
    reported through *warn* once, with the key to add them to, so the omission
    is a decision the user can see rather than a silent one. So are, once, the
    names of listed properties that a built-in or link field already owns.

    :raises ValueError: If a test case occurs more than once across *reports*.
        Its ID is derived from where the test is, so a repeat means the same
        case was reported twice -- typically the same report given twice. A
        needs.json cannot hold two needs with one ID, and keeping either one
        silently would lose evidence, so the caller has to sort out its inputs.
    """
    needs: dict[str, NeedItem] = {}
    duplicates: set[str] = set()
    left_out: set[str] = set()
    collisions: set[str] = set()
    known = set(extra_options) | set(link_properties or {})
    for report_path, suites in reports:
        for suite_name, case in iter_cases(suites):
            properties = case.get("properties")
            if isinstance(properties, Mapping):
                left_out.update(str(name) for name in properties if name not in known)
            need = build_need(
                report_path,
                suite_name,
                case,
                need_type=need_type,
                tags=tags,
                link_properties=link_properties,
                base_url=base_url,
                commit=commit,
                url_pattern=url_pattern,
                fields=fields,
                extra_options=extra_options,
                collisions=collisions,
            )
            need_id = str(need["id"])
            if need_id in needs:
                duplicates.add(need_id)
            needs[need_id] = need
    if duplicates:
        listed = ", ".join(sorted(duplicates))
        raise ValueError(
            f"{len(duplicates)} test case(s) occur more than once across the given "
            f"reports and would collapse into one need each: {listed}. Every case "
            f"must be unique; if the same report was given twice, give it once."
        )
    if left_out and warn is not None:
        warn(
            f"properties not exported: {', '.join(sorted(left_out))}. Only "
            f"properties listed in extra_options become need fields (the build "
            f"accepts exactly those); list them there, or map them to a link "
            f"field with link_properties."
        )
    if collisions and warn is not None:
        warn(
            f"properties not exported, their names are taken by built-in or "
            f"link fields: {', '.join(sorted(collisions))}. The built-in value "
            f"wins; rename the property, or map it to a link field with "
            f"link_properties."
        )

    return {
        "project": project,
        "current_version": version,
        "versions": {
            version: {
                "needs": needs,
                "needs_amount": len(needs),
                # The type of every field the file uses, as sphinx-needs
                # declares the fields of the files it writes itself. Without
                # it the types are knowable only by loading the extension into
                # a Sphinx build, which a consumer of the artifact does not do.
                "needs_schema": case_needs_schema(
                    {**DEFAULT_FIELD_NAMES, **(fields or {})},
                    extra_options=extra_options,
                    link_fields=(link_properties or {}).values(),
                ),
            }
        },
    }
