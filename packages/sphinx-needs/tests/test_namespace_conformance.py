"""Namespaced ids, held to the shared conformance corpus.

``tests/fixtures/namespace_conformance.toml`` is the executable half of the "Namespaced
ids" documentation page. This repository is its repository of record and ubCode is to
vendor it, so every case is a statement both tools are held to. Each case is one project,
built with the ``needs`` builder (or, for a case whose configuration is refused, not
built), and three things are asserted:

* every case's outcome -- how each pinned need is split (``NeedItem.ns`` and
  ``NeedItem.local_id`` of the built environment, which needs.json does not carry),
  whether the version written is marked, the pinned values as ``needs.json`` writes them,
  the needs pinned as not created, the findings as a multiset, and the informational
  notes, one per source read, read from the status stream by their wording;
* the number of cases, so that a trimmed corpus is a red test rather than quietly reduced
  coverage;
* the shape of every case, so that a case without a complete expectation cannot pass by
  saying nothing.

The runner half every such corpus shares is ``sphinx_needs_testkit.conformance``.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs_testkit.conformance import (
    case_files,
    check_values,
    match_findings,
    params,
    read_findings,
)

CORPUS_PATH = Path(__file__).parent / "fixtures" / "namespace_conformance.toml"

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNT = 26

#: The codes compared, as bare subcodes; every other finding is each tool's own.
SHARED_CODES = frozenset(
    {"create_need", "import_need", "load_external_need", "link_outgoing"}
)

#: The informational notes, by the wording sphinx-needs gives them on its status stream.
NOTES = {
    "namespaced_ids_unmarked": re.compile(r"its ids are read as namespaced ids"),
    "namespaced_ids_off": re.compile(r"its ids are read as plain ids"),
}

#: The configuration the runner gives every case besides its ``ubproject.toml``.
CONF_PY = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
"""

#: The title the runner puts above every case's ``source``.
TITLE = "Case\n====\n\n"

KEYS = ("code", "need", "field")


def _corpus() -> list[dict[str, Any]]:
    with CORPUS_PATH.open("rb") as handle:
        return tomllib.load(handle)["case"]


CASES = _corpus()
BUILT = [case for case in CASES if "refused" not in case["expect"]]
REFUSED = [case for case in CASES if "refused" in case["expect"]]


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
    """Every case says why, what it builds and its own need types. A refused case pins
    the name alone; every other pins its findings (``[]`` for none), its notes, whether
    the version written is marked, and at least one need's split."""
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
            "divergent",
            "expect",
        }, name
        assert case["why"] and case["config"] and case["source"], name
        # a registered divergence names the tool's register row; this runner runs it
        assert _divergent_problems(case) == [], name
        assert not (case.get("python_only") and case.get("ubcode_only")), name
        types = tomllib.loads(case["config"])["needs"]["types"]
        assert types, name
        for entry in types.values():
            assert "title" in entry and "prefix" in entry, name
        expect = case["expect"]
        if "refused" in expect:
            assert set(expect) == {"refused"}, name
            assert expect["refused"] in {"ns", "local_id"}, name
            continue
        assert {"findings", "notes", "marked"} <= set(expect), name
        assert set(expect) <= {
            "findings",
            "notes",
            "marked",
            "split",
            "needs",
            "missing",
        }, name
        assert isinstance(expect["marked"], bool), name
        assert expect.get("split"), name
        for pin in expect["split"].values():
            assert set(pin) == {"ns", "local_id"}, name
        # a need pinned as not created is one the source or a file gives
        text = case["source"] + "".join(case.get("files", {}).values())
        for need_id in expect.get("missing", []):
            assert f":id: {need_id}\n" in text or f'"{need_id}":' in text, (
                name,
                need_id,
            )
        for finding in expect["findings"]:
            assert set(finding) <= set(KEYS), name
            assert finding["code"] in SHARED_CODES, name
        assert set(expect["notes"]) <= set(NOTES), name


def _divergent_problems(case: Mapping[str, Any]) -> list[str]:
    """What is wrong with a case's ``divergent`` key: it names ubCode alone, with the
    row of its divergence register as a non-empty string."""
    if "divergent" not in case:
        return []
    divergent = case["divergent"]
    if not isinstance(divergent, dict):
        return [f"divergent is {type(divergent).__name__}, not a table"]
    problems = [
        f"divergent names {tool!r}" for tool in sorted(set(divergent) - {"ubcode"})
    ]
    row = divergent.get("ubcode")
    if not (isinstance(row, str) and row):
        problems.append(f"divergent.ubcode is {row!r}, not a register row")
    return problems


@pytest.mark.parametrize(
    "divergent",
    ["design/x.md", {}, {"ubcode": 1}, {"ubcode": ""}, {"ubcode": "x", "python": "y"}],
)
def test_a_divergent_key_names_only_a_ubcode_register_row(divergent: Any) -> None:
    assert _divergent_problems({"divergent": divergent}) != []
    assert _divergent_problems({"divergent": {"ubcode": "design/x.md#row"}}) == []


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    """ubCode's copy names this path; the header must keep saying this one is canonical."""
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert "packages/sphinx-needs/tests/fixtures/namespace_conformance.toml" in header
    assert "THIS copy is CANONICAL" in header


def _files(case: Mapping[str, Any]) -> list[tuple[Path, str]]:
    """The case's project: its configuration, its document, and its other files."""
    return case_files(case, conf_py=CONF_PY, title=TITLE)


def _notes(status: str) -> Counter[str]:
    """The informational notes of a build, by code."""
    return Counter(
        code
        for line in status.splitlines()
        for code, wording in NOTES.items()
        if wording.search(line)
    )


def test_the_notes_are_read_by_their_wording() -> None:
    """Each note is counted once per line that carries it, and other lines are none."""
    status = (
        "Needs import file a.json: its ids are read as namespaced ids, ...\n"
        "External needs source 'b.json': its ids are read as namespaced ids, ...\n"
        "Needs import file c.json: ... its ids are read as plain ids\n"
        "building [needs]: targets for 1 source files that are out of date\n"
    )
    assert _notes(status) == Counter(
        {"namespaced_ids_unmarked": 2, "namespaced_ids_off": 1}
    )


@pytest.mark.parametrize(
    "test_app,case", params(BUILT, files=_files), indirect=["test_app"]
)
def test_case(test_app: Any, case: dict[str, Any]) -> None:
    app = test_app
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    version = data["versions"][data["current_version"]]
    needs = version["needs"]
    expect = case["expect"]
    problems = check_values(needs, expect)
    if expect["marked"]:
        if version.get("namespaced_ids") is not True:
            problems.append(
                f"namespaced_ids: {version.get('namespaced_ids')!r}, expected true"
            )
    elif "namespaced_ids" in version:
        problems.append(
            f"namespaced_ids: {version['namespaced_ids']!r}, expected no such key"
        )
    found, unread = read_findings(
        app, needs, shared=SHARED_CODES, ubcode_only=frozenset()
    )
    problems += [f"a record naming a shared code is unreadable: {w!r}" for w in unread]
    problems += match_findings(found, expect["findings"], keys=KEYS)
    notes = _notes(app._status.getvalue())
    if notes != Counter(expect["notes"]):
        problems.append(f"notes: {dict(notes)}, expected {expect['notes']}")
    # read after the findings: a view that is not yet resolved resolves the needs again,
    # and reports again what resolving reports
    view = SphinxNeedsData(app.env).get_needs_view()
    for need_id, pin in expect["split"].items():
        if need_id not in view:
            problems.append(f"{need_id}: no such need")
            continue
        need = view[need_id]
        if need.ns != tuple(pin["ns"]) or need.local_id != pin["local_id"]:
            problems.append(
                f"{need_id}: split as ({need.ns!r}, {need.local_id!r}), expected "
                f"({tuple(pin['ns'])!r}, {pin['local_id']!r})"
            )
    assert problems == [], case["why"]


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            case,
            id=case["name"],
            marks=[pytest.mark.skip(reason="ubcode_only")]
            if case.get("ubcode_only")
            else [],
        )
        for case in REFUSED
    ],
)
def test_refused_case(make_app: Any, tmp_path: Path, case: dict[str, Any]) -> None:
    for relative, text in _files(case):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    with pytest.raises(NeedsConfigException) as exc_info:
        make_app("needs", srcdir=tmp_path)
    assert repr(case["expect"]["refused"]) in str(exc_info.value), case["why"]
