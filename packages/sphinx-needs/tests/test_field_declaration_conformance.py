"""Fields per need type, held to the shared conformance corpus.

``tests/fixtures/field_declaration_conformance.toml`` is the executable half of the
"Fields per need type" documentation. This repository is its repository of record and
ubCode vendors it, so every case is a statement both tools are held to. Each case is one
project, built with the ``needs`` builder, and three things are asserted:

* every case's outcome -- the pinned values, as ``needs.json`` writes them (type
  included), with its schema's defaults merged under each record where the version says
  it left them out (``needs_defaults_removed``), as a reader reads them,
  the fields pinned as unset, the fields pinned as absent, the needs pinned as not
  created, the fields a written record pinned as leaving out, the pinned keys of a
  field's schema, and the findings of the per-type declaration contract, as a multiset;
* the number of cases, so that a trimmed corpus is a red test rather than quietly reduced
  coverage;
* the shape of every case, so that a case without a complete expectation cannot pass by
  saying nothing.

The runner half every such corpus shares is ``sphinx_needs_testkit.conformance``; what
is this corpus's own is here: its codes, the need type a finding names, and the reader of
``field_fail`` and ``link_fail``, whose records name neither their need's location nor
their field in a form the warning stream can be read for, and which are read from the
``schema_violations.json`` the validation writes beside ``needs.json`` instead.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs_testkit.conformance import (
    Finding,
    Reader,
    case_files,
    check_schema,
    check_values,
    check_version_values,
    match_findings,
    params,
    read_findings,
)

CORPUS_PATH = Path(__file__).parent / "fixtures" / "field_declaration_conformance.toml"

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNT = 90

#: The cases of the section "an entry naming a default type", the only ones whose
#: ``needs_types`` may hold an entry with neither a ``title`` nor a ``prefix``.
BARE_ENTRY_CASES = frozenset(
    {
        "default-type-entry-narrows-it",
        "default-type-entry-beside-a-declared-type",
        "bare-entry-of-no-default-type-is-ignored",
        "default-type-entry-beside-a-declared-type-has-no-other-default",
    }
)

#: The codes of the per-type declaration contract, compared as bare subcodes; every
#: other finding (a ``needs.config`` warning, a dead link) is each tool's own.
SHARED_CODES = frozenset(
    {
        "type_inherits",
        "type_conflict",
        "type_widening",
        "undeclared_for_type",
        "needextend",
        "derive_authored",
        "derive_invalid",
        "dynamic_function",
        "create_need",
        "field_fail",
        "link_fail",
        "link_target_type",
        "external_link_target_type",
    }
)

#: The codes only ubCode reports: none in this corpus.
UBCODE_ONLY_CODES: frozenset[str] = frozenset()

#: The configuration the runner gives every case besides its ``ubproject.toml``.
CONF_PY = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
"""

#: The title the runner puts above every case's ``source``.
TITLE = "Case\n====\n\n"

#: The positions of a found finding.
KEYS = ("code", "need", "field", "type")

#: the entry a finding of the schema's build names, and the field or link type in it
_ENTRY = re.compile(r"needs_types\['([^']+)'\](?:\.(?:fields|links)\['([^']+)'\])?")
#: the first field, option or link type a message names (a needextend's ``+``/``-``
#: of an option stripped)
_FIELD = re.compile(r"(?:[Ff]ield|[Oo]ption|[Ll]ink type) '[+-]?([^']+)'")
#: the need type a finding names that names no entry, per code
_TYPE = {
    "type_inherits": re.compile(r"^Need type '([^']+)'"),
    "undeclared_for_type": re.compile(r" on need type '([^']+)'"),
    "needextend": re.compile(r" on need type '([^']+)'"),
    # the TARGET need's type, not the source's: the type the link may not point to
    "link_target_type": re.compile(r"target need type '([^']+)'"),
    "external_link_target_type": re.compile(r"target need type '([^']+)'"),
}

#: the default id regex, which every need id of a case satisfies
_NEED_ID = re.compile(r"[A-Z0-9_]{5,}")


def _corpus() -> list[dict[str, Any]]:
    with CORPUS_PATH.open("rb") as handle:
        return tomllib.load(handle)["case"]


CASES = _corpus()


def test_the_corpus_still_has_every_case() -> None:
    assert len(CASES) == EXPECTED_CASE_COUNT, (
        f"{CORPUS_PATH.name} carries {len(CASES)} cases, expected "
        f"{EXPECTED_CASE_COUNT}. Adding a case means raising EXPECTED_CASE_COUNT; "
        "anything else means cases were lost."
    )


def test_every_case_name_is_unique() -> None:
    names = Counter(case["name"] for case in CASES)
    assert [name for name, count in names.items() if count > 1] == []


def test_every_case_has_a_complete_expectation() -> None:
    """Every case says why, what it builds, its own need types, the findings (``[]``
    for none), and at least one pinned value; it runs in at least one tool."""
    for case in CASES:
        name = case["name"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), name
        assert set(case) <= {
            "name",
            "why",
            "config",
            "source",
            "files",
            "python_only",
            "ubcode_only",
            "expect",
        }, name
        assert case["why"] and case["config"] and case["source"], name
        assert not (case.get("python_only") and case.get("ubcode_only")), name
        # the default need types are replaced by a `needs_types` declaring a type: a
        # case declares every type it uses, each with a title and a prefix, but for a
        # bare entry (neither) in the section "an entry naming a default type", which
        # narrows a default type or is ignored, and names no `need`, a default type of
        # sphinx-needs only
        types = tomllib.loads(case["config"])["needs"]["types"]
        entries = (
            list(types.items())
            if isinstance(types, dict)
            else [(entry.get("directive"), entry) for entry in types]
        )
        assert entries, name
        for directive, entry in entries:
            assert ("title" in entry) == ("prefix" in entry), (name, directive)
            assert "title" in entry or (
                name in BARE_ENTRY_CASES and directive != "need"
            ), (name, directive)
        expect = case["expect"]
        assert "findings" in expect, name
        assert set(expect) <= {
            "needs",
            "nulls",
            "absent",
            "missing",
            "omitted",
            "schema",
            "findings",
        }, name
        assert any(
            expect.get(key) for key in ("needs", "nulls", "absent", "missing")
        ), name
        for table in ("needs", "nulls", "absent", "missing", "omitted"):
            for need_id in expect.get(table, {}):
                assert _NEED_ID.fullmatch(need_id), (name, need_id)
        # a need pinned as not created is one the source gives, so a typo cannot pass
        for need_id in expect.get("missing", []):
            assert f":id: {need_id}\n" in case["source"], (name, need_id)
        for finding in expect["findings"]:
            assert set(finding) <= set(KEYS), name
            assert finding["code"] in SHARED_CODES, name


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    """ubCode's copy names this path; the header must keep saying this one is canonical."""
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert (
        "packages/sphinx-needs/tests/fixtures/field_declaration_conformance.toml"
        in header
    )
    assert "THIS copy is CANONICAL" in header


def _files(case: Mapping[str, Any]) -> list[tuple[Path, str]]:
    """The case's project: its configuration, its document, and its other files."""
    return case_files(case, conf_py=CONF_PY, title=TITLE)


@pytest.mark.parametrize(
    "relative", ["../x.json", "/x.json", "a/../../x.json", "C:/x.json"]
)
def test_a_case_cannot_write_outside_its_directory(relative: str) -> None:
    with pytest.raises(AssertionError, match="outside the case directory"):
        _files({"config": "", "source": "", "files": {relative: "{}"}})


def test_an_omitted_pin_reads_the_written_record() -> None:
    """An ``omitted`` pin holds only where the record as written lacks the field and a
    schema default restores it; the other pins read the record with the defaults merged."""
    expect = {"omitted": {"REQ_001": ["asil"]}, "needs": {"REQ_001": {"asil": "QM"}}}
    defaults = {"asil": "QM"}
    assert check_values({"REQ_001": {}}, expect, defaults=defaults) == []
    assert check_values({"REQ_001": {"asil": "QM"}}, expect, defaults=defaults) == [
        "REQ_001.asil: written as 'QM', expected left out"
    ]
    assert check_values({"REQ_001": {}}, expect) == [
        "REQ_001.asil: None, expected 'QM'",
        "REQ_001.asil: left out, and no default restores it",
    ]
    assert check_values({}, expect, defaults=defaults) == [
        "REQ_001: no such need",
        "REQ_001: no such need",
    ]


def test_an_omitted_pin_needs_a_version_that_says_it_left_defaults_out() -> None:
    """Defaults are merged only under a version whose ``needs_defaults_removed`` is
    true, and an ``omitted`` pin fails on any other version."""
    schema = {"properties": {"asil": {"default": "QM"}}}
    expect = {"omitted": {"REQ_001": ["asil"]}, "needs": {"REQ_001": {"asil": "QM"}}}
    removed = {"needs_defaults_removed": True, "needs_schema": schema}
    assert check_version_values({**removed, "needs": {"REQ_001": {}}}, expect) == []
    silent = {"needs_schema": schema, "needs": {"REQ_001": {}}}
    assert check_version_values(silent, expect) == [
        "needs_defaults_removed: None, expected true (the case pins fields left out)",
        "REQ_001.asil: None, expected 'QM'",
        "REQ_001.asil: left out, and no default restores it",
    ]
    # only `true` says it: a truthy flag of another JSON type merges nothing
    truthy = {**removed, "needs_defaults_removed": 1, "needs": {"REQ_001": {}}}
    assert check_version_values(truthy, expect)[0] == (
        "needs_defaults_removed: 1, expected true (the case pins fields left out)"
    )
    # without the flag a record leaving a pinned key out fails, as before any merge
    assert check_version_values(silent, {"needs": {"REQ_001": {"asil": "QM"}}}) == [
        "REQ_001.asil: None, expected 'QM'"
    ]


def _describe(code: str, message: str) -> tuple[str | None, str | None]:
    """The field and the need type a finding names.

    A finding of the schema's build names its entry, ``needs_types['<t>']``, and the
    field or link type in it, ``.fields['<f>']`` or ``.links['<f>']``; any other names
    its field as ``Field``/``Option``/``Link type '<f>'`` (or a link's ``field '<l>'``),
    and its type as its code says (``Need type '<t>'`` for ``type_inherits``;
    ``on need type '<t>'`` for ``undeclared_for_type`` and ``needextend``; the TARGET's
    ``target need type '<t>'`` for ``link_target_type`` and
    ``external_link_target_type``).
    """
    field = _FIELD.search(message)
    field_name = field[1] if field else None
    entry = _ENTRY.search(message)
    if entry is not None:
        return entry[2] or field_name, entry[1]
    need_type = _TYPE[code].search(message) if code in _TYPE else None
    return field_name, need_type[1] if need_type else None


def _violations(subtype: str) -> Reader:
    """The reader of the schema validation's findings of *subtype* (``field_fail``,
    ``link_fail``), from the ``schema_violations.json`` the validation writes beside
    ``needs.json`` (``sphinx_needs.schema.process``): its ``validation_warnings`` maps a
    need id to that need's violations, each with its ``subtype`` and the field or link
    type in its ``details``. The file is written on every build that validates, so its
    absence fails the case; a build whose configuration switches the validation off
    (``schema_validation_enabled = false``) has neither the file nor these findings."""

    def read(app: Any, needs: Mapping[str, Mapping[str, Any]]) -> Iterator[Finding]:
        if not app.config.needs_schema_validation_enabled:
            return
        report = json.loads(
            Path(app.outdir, "schema_violations.json").read_text(encoding="utf-8")
        )
        for need_id, violations in report["validation_warnings"].items():
            for violation in violations:
                if violation["subtype"] == subtype:
                    yield (subtype, need_id, violation["details"].get("field"), None)

    return read


@pytest.mark.parametrize(
    "test_app,case", params(CASES, files=_files), indirect=["test_app"]
)
def test_case(test_app: Any, case: dict[str, Any]) -> None:
    app = test_app
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    version = data["versions"][data["current_version"]]
    needs = version["needs"]
    expect = case["expect"]
    problems = check_version_values(version, expect)
    problems += check_schema(version["needs_schema"]["properties"], expect)
    found, unread = read_findings(
        app,
        needs,
        shared=SHARED_CODES,
        ubcode_only=UBCODE_ONLY_CODES,
        describe=_describe,
        readers={code: _violations(code) for code in ("field_fail", "link_fail")},
    )
    problems += [f"a record naming a shared code is unreadable: {w!r}" for w in unread]
    problems += match_findings(found, expect["findings"], keys=KEYS)
    assert problems == [], case["why"]
