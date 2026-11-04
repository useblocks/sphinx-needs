"""Need templates, held to the shared conformance corpus.

``tests/fixtures/need_templates_conformance.toml`` is the executable half of the need
template options of the ``need`` directive (``:template:``, ``:pre_template:``,
``:post_template:`` and ``:jinja_content:``). This repository is its repository of record
and ubCode vendors it, so every case is a statement both tools are held to. Each case is
one project, built with the ``needs`` builder, and three things are asserted:

* every case's outcome -- the pinned values of each need as ``needs.json`` writes them
  (its ``content``, ``pre_content``, ``post_content``, ``doctype`` and template keys,
  type included), the fields pinned as unset, the needs pinned as not created, and the
  findings of the need-template contract, as a multiset;
* the number of cases, so that a trimmed corpus is a red test rather than quietly reduced
  coverage;
* the shape of every case, so that a case without a complete expectation cannot pass by
  saying nothing.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import tomllib
from collections import Counter
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from sphinx_needs_testkit.conformance import (
    check_values,
    inside,
    match_findings,
    params,
    read_findings,
)

CORPUS_PATH = Path(__file__).parent / "fixtures" / "need_templates_conformance.toml"

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNT = 32

#: The codes of the need-template contract, compared as bare subcodes; every other
#: finding (a dead link, a need that could not be imported) is each tool's own.
SHARED_CODES = frozenset(
    {
        "template_missing",
        "template_syntax",
        "template_render",
        "template_undefined",
        "template_unresolved",
        "template_heading",
        "deprecated_jinja_content",
    }
)

#: The codes only ubCode reports: compared in a ``ubcode_only`` case alone, and dropped
#: before comparing in every other case. ``template_heading`` is ubCode's refusal of a
#: heading in pre/post template output, which sphinx-needs turns into a section.
UBCODE_ONLY_CODES = frozenset({"template_heading"})

#: The configuration the runner gives every case besides its ``ubproject.toml``, which
#: is one directory up for each part of a case's ``srcdir``.
CONF_PY = """\
extensions = ["sphinx_needs", "myst_parser"]
needs_from_toml = "{toml}"
needs_build_json = True
"""

#: The title the runner puts above every case's ``source``.
TITLE = "Case\n====\n\n"

#: The title the runner puts above every case's ``source_md``.
MD_TITLE = "# Page\n\n"

#: What the runner puts below a case's ``source`` when the case has a ``source_md``, so
#: that the MyST page is in the toctree.
TOCTREE = "\n.. toctree::\n   :hidden:\n\n   page\n"

#: The field a ``template_unresolved`` message names.
_FIELD = re.compile(r"[Ff]ield '([^']+)'")


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
    one pinned need; it runs in at least one tool, and it carries a template."""
    for case in CASES:
        name = case["name"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), name
        assert set(case) <= {
            "name",
            "why",
            "rules",
            "config",
            "source",
            "source_md",
            "srcdir",
            "files",
            "python_only",
            "ubcode_only",
            "expect",
        }, name
        assert case["why"] and case["source"], name
        assert "config" in case, name
        assert case.get("rules"), name
        assert all(isinstance(rule, int) for rule in case["rules"]), name
        assert not (case.get("python_only") and case.get("ubcode_only")), name
        if "srcdir" in case:
            # a subdirectory of the case directory, which the case's own
            # `ubproject.toml` names as its source directory, as ubCode reads it
            srcdir = case["srcdir"]
            assert srcdir and inside(srcdir) != Path(), name
            assert tomllib.loads(case["config"])["source"]["dir"] == srcdir, name
        expect = case["expect"]
        assert "findings" in expect, name
        assert set(expect) <= {"needs", "nulls", "missing", "findings"}, name
        assert expect.get("needs") or expect.get("nulls"), name
        for finding in expect["findings"]:
            assert set(finding) <= {"code", "need", "field"}, name
            assert finding["code"] in SHARED_CODES, name
            # a code only ubCode reports is compared in a case only ubCode runs
            assert finding["code"] not in UBCODE_ONLY_CODES or case.get(
                "ubcode_only"
            ), name


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    """ubCode's copy names this path; the header must keep saying this one is canonical,
    and name the engine and the sphinx-needs version it was recorded against."""
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert (
        "packages/sphinx-needs/tests/fixtures/need_templates_conformance.toml" in header
    )
    assert "THIS copy is CANONICAL" in header
    assert re.search(r"^# minijinja: \d+\.\d+\.\d+$", header, re.MULTILINE)
    assert re.search(r"^# sphinx-needs: \d+\.\d+\.\d+", header, re.MULTILINE)


def test_the_corpus_names_the_engine_it_runs_on() -> None:
    """The ``# minijinja:`` line is the version the cases were recorded against, and the
    lockstep hook ubCode's runner asserts: a minijinja bump that changes it is a corpus
    re-record, not a silent drift."""
    header = CORPUS_PATH.read_text(encoding="utf-8")
    match = re.search(r"^# minijinja: (\S+)$", header, re.MULTILINE)
    assert match is not None
    assert match[1] == importlib.metadata.version("minijinja")


def _files(case: Mapping[str, Any]) -> list[tuple[Path, str]]:
    """The case's project: the runner's ``conf.py``, the case's ``config`` as its
    ``ubproject.toml``, its ``source`` under a title as ``index.rst``, its
    ``source_md`` under a title as ``page.md``, and its other ``files``."""
    srcdir = PurePosixPath(case["srcdir"]) if case.get("srcdir") else None
    toml = "../" * len(srcdir.parts) if srcdir else ""
    root = inside(str(srcdir)) if srcdir else Path()
    index = TITLE + case["source"]
    files = [
        (root / "conf.py", CONF_PY.replace("{toml}", toml + "ubproject.toml")),
        (Path("ubproject.toml"), case["config"]),
    ]
    if "source_md" in case:
        index += TOCTREE
        files.append((root / "page.md", MD_TITLE + case["source_md"]))
    files.append((root / "index.rst", index))
    files += [(inside(rel), text) for rel, text in case.get("files", {}).items()]
    return files


@pytest.mark.parametrize(
    "relative", ["../x.json", "/x.json", "a/../../x.json", "C:/x.json"]
)
def test_a_case_cannot_write_outside_its_directory(relative: str) -> None:
    with pytest.raises(AssertionError, match="outside the case directory"):
        _files({"config": "", "source": "", "files": {relative: "{}"}})


def _describe(code: str, message: str) -> tuple[str | None]:
    """The field a finding is about: only ``template_unresolved`` names one."""
    if code != "template_unresolved":
        return (None,)
    field = _FIELD.search(message)
    return (field[1] if field else None,)


@pytest.mark.parametrize(
    "test_app,case",
    params(CASES, files=_files),
    indirect=["test_app"],
)
def test_case(test_app: Any, case: dict[str, Any]) -> None:
    app = test_app
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = data["versions"][data["current_version"]]["needs"]
    expect = case["expect"]
    problems = check_values(needs, expect)
    found, unread = read_findings(
        app,
        needs,
        shared=SHARED_CODES,
        ubcode_only=UBCODE_ONLY_CODES,
        describe=_describe,
    )
    problems += [f"a record naming a shared code is unreadable: {w!r}" for w in unread]
    problems += match_findings(found, expect["findings"])
    assert problems == [], case["why"]
