"""Declared derived fields, held to the shared conformance corpus.

``tests/fixtures/derive_conformance.toml`` is the executable half of the "Derived fields"
documentation. This repository is its repository of record and ubCode vendors it, so
every case is a statement both tools are held to. Each case is one project, built with
the ``needs`` builder, and three things are asserted:

* every case's outcome -- the pinned values, as ``needs.json`` writes them (type
  included), the fields pinned as unset, and the findings of the derived-field contract,
  as a multiset;
* the number of cases, so that a trimmed corpus is a red test rather than quietly reduced
  coverage;
* the shape of every case, so that a case without a complete expectation cannot pass by
  saying nothing.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs_testkit.conformance import (
    case_files,
    check_values,
    match_findings,
    params,
    read_findings,
)

CORPUS_PATH = Path(__file__).parent / "fixtures" / "derive_conformance.toml"

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNT = 91

#: The codes of the derived-field contract, compared as bare subcodes; every other
#: finding (a dead link, a deprecated option) is each tool's own.
SHARED_CODES = frozenset(
    {
        "derive_invalid",
        "derive_authored",
        "derive_unique",
        "derive_cycle",
        "derive_scope",
        "derive_dense",
        "dynamic_function",
        "derive_sphinx_minimum",
    }
)

#: The codes only ubCode reports: compared in a ``ubcode_only`` case alone, and dropped
#: before comparing in every other case. ``derive_sphinx_minimum`` is ubCode's notice
#: that a project declares ``derive``, once per project, so it fires in nearly every
#: case; sphinx-needs has no such finding.
UBCODE_ONLY_CODES = frozenset({"derive_sphinx_minimum"})

#: The configuration the runner gives every case besides its ``ubproject.toml``.
CONF_PY = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
"""

#: The title the runner puts above every case's ``source``.
TITLE = "Case\n====\n\n"


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
    """Every case says why, what it builds, the findings (``[]`` for none), and at least
    one pinned value; it runs in at least one tool."""
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
        expect = case["expect"]
        assert "findings" in expect, name
        assert set(expect) <= {"needs", "nulls", "findings"}, name
        assert expect.get("needs") or expect.get("nulls"), name
        for finding in expect["findings"]:
            assert set(finding) <= {"code", "need", "field"}, name
            assert finding["code"] in SHARED_CODES, name
            # a code only ubCode reports is compared in a case only ubCode runs
            assert finding["code"] not in UBCODE_ONLY_CODES or case.get(
                "ubcode_only"
            ), name


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    """ubCode's copy names this path; the header must keep saying this one is canonical."""
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert "packages/sphinx-needs/tests/fixtures/derive_conformance.toml" in header
    assert "THIS copy is CANONICAL" in header


def _files(case: dict[str, Any]) -> list[tuple[Path, str]]:
    """The case's project: its configuration, its document, and its other files."""
    return case_files(case, conf_py=CONF_PY, title=TITLE)


@pytest.mark.parametrize(
    "relative", ["../x.json", "/x.json", "a/../../x.json", "C:/x.json"]
)
def test_a_case_cannot_write_outside_its_directory(relative: str) -> None:
    with pytest.raises(AssertionError, match="outside the case directory"):
        _files({"config": "", "source": "", "files": {relative: "{}"}})


@pytest.mark.parametrize(
    "test_app,case", params(CASES, files=_files), indirect=["test_app"]
)
def test_case(test_app: Any, case: dict[str, Any]) -> None:
    app = test_app
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = data["versions"][data["current_version"]]["needs"]
    expect = case["expect"]
    problems = check_values(needs, expect)
    found, unread = read_findings(
        app, needs, shared=SHARED_CODES, ubcode_only=UBCODE_ONLY_CODES
    )
    problems += [f"a record naming a shared code is unreadable: {w!r}" for w in unread]
    problems += match_findings(found, expect["findings"])
    assert problems == [], case["why"]
