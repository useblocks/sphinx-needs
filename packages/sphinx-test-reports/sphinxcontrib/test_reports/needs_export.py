"""Turn parsed test reports into a needs.json payload.

Sphinx-free: the conversion runs as a build action, and the documentation build
only imports the result.

Two rules shape the output:

* **Every field is always present.** Absent XML attributes become empty values
  rather than missing keys, so a schema can simply require a field and a
  consumer never has to distinguish "unset" from "absent".
* **Nothing depends on the wall clock or on dict ordering**, so the file is a
  cacheable build artifact and a diffable piece of evidence.
"""

import re
from typing import Iterable, Iterator, Mapping, Sequence, Union

from sphinxcontrib.test_reports.identity import (
    UNKNOWN,
    case_display_name,
    deterministic_case_id,
)
from sphinxcontrib.test_reports.remote import DEFAULT_URL_PATTERN, source_url

#: A need field value as it appears in needs.json.
FieldValue = Union[str, list[str]]
NeedItem = dict[str, FieldValue]

#: Version key used when the caller does not supply one. needs.json requires a
#: ``current_version``, but a converted report has no baseline history.
DEFAULT_VERSION = "1.0"

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_WHITESPACE = re.compile(r"\s+")

#: The parser keeps the historical spelling ``failure`` -- it is a documented
#: need field value and a CSS class. Exported data has no such obligation and
#: uses the migration-target vocabulary (passed|failed|error|skipped|disabled),
#: which is also what S-CORE's metamodel spells.
RESULT_NAMES = {"failure": "failed"}


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
    """An RST literal block, indented so the need content stays valid."""
    indented = "\n".join(f"   {line.lstrip()}" for line in body.split("\n"))
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


def _optional(value: object, absent: object) -> str:
    """String form of an attribute, empty when the parser reported it absent."""
    return "" if value is None or value == absent else str(value)


def _mappings(value: object) -> list[Mapping[str, object]]:
    """Typed view over a list of dicts coming from the parser."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _iter_cases(
    suites: Iterable[Mapping[str, object]],
) -> Iterator[tuple[str, Mapping[str, object]]]:
    """Yield ``(suite_name, case)`` pairs, descending into nested suites."""
    for suite in suites:
        name = str(suite.get("name", ""))
        for case in _mappings(suite.get("testcases")):
            yield name, case
        yield from _iter_cases(_mappings(suite.get("testsuite_nested")))


def build_need(
    suite_name: str,
    case: Mapping[str, object],
    *,
    need_type: str = "testcase",
    tags: Sequence[str] = (),
    link_properties: Mapping[str, str] | None = None,
    base_url: str = "",
    commit: str = "",
    url_pattern: str = DEFAULT_URL_PATTERN,
) -> NeedItem:
    """One test case as a need item."""
    link_properties = link_properties or {}

    classname = _optional(case.get("classname"), UNKNOWN)
    name = _optional(case.get("name"), UNKNOWN)
    source_file = _optional(case.get("file"), UNKNOWN)
    source_line = _optional(case.get("line"), -1)
    time = _optional(case.get("time"), -1)

    url = source_url(base_url, commit, source_file, source_line, url_pattern)

    need: NeedItem = {
        "id": deterministic_case_id(
            classname=classname, name=name, file=source_file, prefix=need_type
        ),
        "type": need_type,
        "title": case_display_name(classname, name),
        "content": build_content(case),
        "tags": list(tags),
        "name": name,
        "classname": classname,
        "suite": suite_name,
        "file": source_file,
        "line": source_line,
        "time": time,
        "result": RESULT_NAMES.get(
            str(case.get("result", "")), str(case.get("result", ""))
        ),
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

    for property_name, value in properties.items():
        if property_name in link_properties or property_name in need:
            continue
        need[property_name] = str(value)

    return need


def build_needs_file(
    suites: Iterable[Mapping[str, object]],
    *,
    project: str = "",
    version: str = DEFAULT_VERSION,
    need_type: str = "testcase",
    tags: Sequence[str] = (),
    link_properties: Mapping[str, str] | None = None,
    base_url: str = "",
    commit: str = "",
    url_pattern: str = DEFAULT_URL_PATTERN,
) -> dict[str, object]:
    """The complete needs.json payload for a set of parsed reports.

    No ``created`` key is written: a wall clock inside a cacheable build output
    would change the file on every run.
    """
    needs: dict[str, NeedItem] = {}
    for suite_name, case in _iter_cases(suites):
        need = build_need(
            suite_name,
            case,
            need_type=need_type,
            tags=tags,
            link_properties=link_properties,
            base_url=base_url,
            commit=commit,
            url_pattern=url_pattern,
        )
        needs[str(need["id"])] = need

    return {
        "project": project,
        "current_version": version,
        "versions": {
            version: {
                "needs": needs,
                "needs_amount": len(needs),
            }
        },
    }
