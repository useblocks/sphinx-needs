"""Nested ``<testsuite>`` elements at every depth (#2050).

A JUnit report's suite may hold suites of its own (Ant, Maven, pytest's
``pytest_nested_example.xml``). The directives used to crash on one -- ``KeyError:
'testsuites'``, a key the parser never writes -- and ``test-results`` showed a suite that
also held nested suites with an empty table, because the parser kept either a suite's
nested suites or its own cases, never both.

The rules are ubCode's (useblocks/ubcode#3909, #3924), so the two tools mint the same ids
and links for the same report:

- ``:auto_suites:`` mints every suite at every depth in pre-order: the suite, then (with
  ``:auto_cases:``) its DIRECT cases, then its nested suites the same way;
- a suite's id is ``{parent id}_{SHA1(name)[:tr_suite_id_length]}``, the parent being the
  file for a top-level suite and the enclosing suite for a nested one;
- a suite links its parent and every ancestor up to the file; a case links its suite and
  that same chain;
- a hand-written ``:suite:`` finds the first top-level suite of the name, else the first
  of that name at any depth in pre-order;
- ``test-results`` shows a nested suite as a section inside its parent's, after the
  parent's own table.
"""

import io
import json
import re
from pathlib import Path

import pytest
from docutils import nodes

#: ubCode's expected needs for its shared fixture's page ``docs/nested.rst`` (the page is
#: ``doc_test/nested_parity/nested.rst`` verbatim), as ``(id, type, title, links)``: read
#: from useblocks/ubcode ``e9fe0b2b16``,
#: ``rust/ubc_parser_ctrl/tests/build_fixtures/test_reports_auto/__expected__/needs.json``.
UBCODE_NESTED_NEEDS = {
    ("TF_NEST", "testfile", "Nested suites", ()),
    ("TF_NEST_42F", "testsuite", "parent_testsuite", ("TF_NEST",)),
    (
        "TF_NEST_42F_41F",
        "testsuite",
        "nested_example",
        ("TF_NEST", "TF_NEST_42F"),
    ),
    (
        "TF_NEST_42F_41F_BCA04",
        "testcase",
        "FLAKE8",
        ("TF_NEST", "TF_NEST_42F", "TF_NEST_42F_41F"),
    ),
    (
        "TF_NEST_42F_41F_D962E",
        "testcase",
        "FLAKE8",
        ("TF_NEST", "TF_NEST_42F", "TF_NEST_42F_41F"),
    ),
    (
        "TF_NEST_42F_2A8",
        "testsuite",
        "nested_pytest_suite",
        ("TF_NEST", "TF_NEST_42F"),
    ),
    (
        "TF_NEST_42F_2A8_03B18",
        "testcase",
        "FLAKE8",
        ("TF_NEST", "TF_NEST_42F", "TF_NEST_42F_2A8"),
    ),
    (
        "TF_NEST_42F_2A8_D9167",
        "testcase",
        "FLAKE8",
        ("TF_NEST", "TF_NEST_42F", "TF_NEST_42F_2A8"),
    ),
    (
        "TF_NEST_42F_2A8_8E5DB",
        "testcase",
        "FLAKE8",
        ("TF_NEST", "TF_NEST_42F", "TF_NEST_42F_2A8"),
    ),
    (
        "TF_NEST_42F_2A8_E5144",
        "testcase",
        "FLAKE8",
        ("TF_NEST", "TF_NEST_42F", "TF_NEST_42F_2A8"),
    ),
    ("TS_NESTED_HAND", "testsuite", "A nested suite by hand", ()),
}


def _needs(app) -> dict:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _rows(needs: dict, docname: str) -> set:
    return {
        (n["id"], n["type"], n["title"], tuple(sorted(n["links"])))
        for n in needs.values()
        if n["docname"] == docname
    }


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/nested_parity"}],
    indirect=True,
)
def test_nested_expansion_equals_ubcode(test_app):
    """B2, the parity pin: every need ubCode mints from its fixture's page, and nothing
    else -- ids, types, titles and links."""
    app = test_app
    app.build()

    assert _rows(_needs(app), "nested") == UBCODE_NESTED_NEEDS


#: The expansion of ``nested_mixed.xml`` by the same formula: ``outer`` (``B14``) holds two
#: cases and ``inner`` (``D2A``), and the second top-level suite is also called ``inner`` --
#: so it is ``TF_MIX_D2A`` beside the nested ``TF_MIX_B14_D2A``.
MIXED_NEEDS = {
    ("TF_MIX", "testfile", "Mixed", ()),
    ("TF_MIX_B14", "testsuite", "outer", ("TF_MIX",)),
    ("TF_MIX_B14_DA820", "testcase", "test_first", ("TF_MIX", "TF_MIX_B14")),
    ("TF_MIX_B14_78FC7", "testcase", "test_second", ("TF_MIX", "TF_MIX_B14")),
    ("TF_MIX_B14_D2A", "testsuite", "inner", ("TF_MIX", "TF_MIX_B14")),
    (
        "TF_MIX_B14_D2A_B035E",
        "testcase",
        "test_nested",
        ("TF_MIX", "TF_MIX_B14", "TF_MIX_B14_D2A"),
    ),
    ("TF_MIX_D2A", "testsuite", "inner", ("TF_MIX",)),
    ("TF_MIX_D2A_65A49", "testcase", "test_top_level", ("TF_MIX", "TF_MIX_D2A")),
}


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/nested_mixed_expansion"}],
    indirect=True,
)
def test_mixed_expansion_mints_direct_cases_and_nested_suites(test_app):
    """B2 on a suite with BOTH direct cases and a nested suite: its cases are minted, the
    nested suite is a child of it, and the LATER top-level suite links only the file --
    nothing of the earlier suite's chain leaks into it. Tags propagate to every need."""
    app = test_app
    app.build()

    needs = _needs(app)
    assert _rows(needs, "index") == MIXED_NEEDS
    assert all("nested" in n["tags"] for n in needs.values())
    assert needs["TF_MIX_B14_DA820"]["suite"] == "outer"
    assert needs["TF_MIX_B14_D2A_B035E"]["suite"] == "inner"
    assert needs["TF_MIX_D2A_65A49"]["suite"] == "inner"


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/nested_lookup"}],
    indirect=True,
)
def test_a_hand_written_suite_finds_a_nested_suite_and_prefers_the_top_level(test_app):
    """B3: ``:suite:`` names a suite that exists only nested -> found (the suite and one
    of its cases mint, ids as written); a name that exists nested AND at the top level ->
    the top-level suite, though the nested one comes first in pre-order."""
    app = test_app
    app.build()

    needs = _needs(app)
    assert needs["TS_HAND"]["suite"] == "nested_example"
    assert needs["TS_HAND"]["cases"] == 10
    assert needs["TC_HAND"]["suite"] == "nested_example"
    assert needs["TC_HAND"]["classname"] == "docs.conf"

    # The top-level `inner` skipped its one case; the nested `inner` skipped none.
    assert needs["TS_INNER"]["skipped"] == 1
    assert needs["TC_INNER"]["case"] == "test_top_level"


def _section(doctree: nodes.document, section_id: str) -> nodes.section:
    found = [s for s in doctree.findall(nodes.section) if section_id in s["ids"]]
    assert len(found) == 1, f"no single section with id {section_id!r}"
    return found[0]


def _body_rows(section: nodes.section) -> list[str]:
    """The ``name`` cells of the table that is a DIRECT child of ``section``."""
    tables = [c for c in section.children if isinstance(c, nodes.table)]
    assert len(tables) == 1
    return [
        row[1].astext() for row in next(iter(tables[0].findall(nodes.tbody))).children
    ]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/nested_results"}],
    indirect=True,
)
def test_test_results_shows_nested_suites_inside_their_parent(test_app):
    """B4: the parent's counters, ``Time:`` and a table of its two DIRECT cases, then
    the nested suite's section, inside the parent's; the second top-level suite is a
    sibling of the parent."""
    app = test_app
    app.build()

    doctree = app.env.get_doctree("results")
    page = _section(doctree, "results")
    top = [c for c in page.children if isinstance(c, nodes.section)]
    assert [s[0].astext() for s in top] == ["outer", "inner"]
    outer, second = top

    kinds = [type(c).__name__ for c in outer.children]
    assert kinds == ["title", "paragraph", "paragraph", "table", "section"]
    assert outer[1].astext() == "Tests: 3, Failures: 1, Errors: 0, Skips: 0"
    assert outer[2].astext() == "Time: 0.6"
    assert _body_rows(outer) == ["test_first", "test_second"]

    nested = outer[4]
    assert nested[0].astext() == "inner"
    assert _body_rows(nested) == ["test_nested"]
    assert _body_rows(second) == ["test_top_level"]

    html = Path(app.outdir, "results.html").read_text(encoding="utf-8")
    assert re.search(r'<section id="inner">\s*<h3>inner<a class="headerlink"', html)


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/nested_results"}],
    indirect=True,
)
def test_the_file_need_counts_top_level_suites(test_app):
    """B6 control: a file need's ``suites`` is the number of TOP-LEVEL suites and its
    counters are the sum of theirs -- unchanged from master."""
    app = test_app
    app.build()

    need = _needs(app)["TF_GTEST"]
    assert (need["suites"], need["cases"]) == (2, 5)
    # Master's values, ``-1`` "absent" sentinels summed in (#2054 is a later round).
    assert (need["passed"], need["failed"], need["skipped"], need["errors"]) == (
        4,
        1,
        -2,
        0,
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/pytest_6_2"}],
    indirect=True,
)
def test_the_counters_line_of_a_flat_report_is_unchanged(test_app):
    """B6 control: a flat report's counters line, byte for byte."""
    app = test_app
    app.build()

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "<p>Tests: 6, Failures: 2, Errors: 0, Skips: 3</p>" in html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/auto_cases_only",
            "warning": io.StringIO(),
        }
    ],
    indirect=True,
)
def test_auto_cases_without_auto_suites_is_still_an_error(test_app):
    """B7 control: ``:auto_cases:`` alone is a configuration error, as before -- since
    #2052 a located ``test_reports.option_invalid`` warning, not a raised
    ``TestReportIncompleteConfigurationError``: the file's need is created, nothing is
    expanded."""
    test_app.build()

    assert (
        "index.rst:4: WARNING: option auto_cases must be used together with auto_suites"
        in test_app._warning.getvalue()
    )
    assert sorted(_needs(test_app)) == ["TF_CASES_ONLY"]


#: The expansion of ``nested_deep.xml`` (three levels; a direct case after a nested suite;
#: ``inner`` under two parents; a second top-level suite) as ``(id, type, title, links)``.
#: A regression pin, not a parity pin -- ubCode has no fixture for this report -- but equal to
#: ubCode ``e9fe0b2b16`` on the same report, measured by the trfix review in both id schemes.
DEEP_NEEDS = {
    ("REQ_1", "req", "A requirement", ()),
    ("TF_DEEP", "testfile", "Deep report", ("REQ_1",)),
    ("TF_DEEP_B14", "testsuite", "outer", ("REQ_1", "TF_DEEP")),
    ("TF_DEEP_B14_9851F", "testcase", "test_o1", ("REQ_1", "TF_DEEP", "TF_DEEP_B14")),
    ("TF_DEEP_B14_DC6D6", "testcase", "test_o2", ("REQ_1", "TF_DEEP", "TF_DEEP_B14")),
    ("TF_DEEP_B14_F23", "testsuite", "mid", ("REQ_1", "TF_DEEP", "TF_DEEP_B14")),
    (
        "TF_DEEP_B14_F23_3455F",
        "testcase",
        "test_m1",
        ("REQ_1", "TF_DEEP", "TF_DEEP_B14", "TF_DEEP_B14_F23"),
    ),
    (
        "TF_DEEP_B14_F23_1C856",
        "testcase",
        "test_m2",
        ("REQ_1", "TF_DEEP", "TF_DEEP_B14", "TF_DEEP_B14_F23"),
    ),
    (
        "TF_DEEP_B14_F23_D2A",
        "testsuite",
        "inner",
        ("REQ_1", "TF_DEEP", "TF_DEEP_B14", "TF_DEEP_B14_F23"),
    ),
    (
        "TF_DEEP_B14_F23_D2A_51668",
        "testcase",
        "test_i1",
        ("REQ_1", "TF_DEEP", "TF_DEEP_B14", "TF_DEEP_B14_F23", "TF_DEEP_B14_F23_D2A"),
    ),
    (
        "TF_DEEP_B14_F23_D2A_A5614",
        "testcase",
        "test_i2[a-1]",
        ("REQ_1", "TF_DEEP", "TF_DEEP_B14", "TF_DEEP_B14_F23", "TF_DEEP_B14_F23_D2A"),
    ),
    ("TF_DEEP_B14_DBE", "testsuite", "mid2", ("REQ_1", "TF_DEEP", "TF_DEEP_B14")),
    (
        "TF_DEEP_B14_DBE_6E55A",
        "testcase",
        "test_x",
        ("REQ_1", "TF_DEEP", "TF_DEEP_B14", "TF_DEEP_B14_DBE"),
    ),
    ("TF_DEEP_352", "testsuite", "second", ("REQ_1", "TF_DEEP")),
    ("TF_DEEP_352_011FC", "testcase", "test_s1", ("REQ_1", "TF_DEEP", "TF_DEEP_352")),
    ("TF_DEEP_352_D2A", "testsuite", "inner", ("REQ_1", "TF_DEEP", "TF_DEEP_352")),
    (
        "TF_DEEP_352_D2A_C63AD",
        "testcase",
        "test_si",
        ("REQ_1", "TF_DEEP", "TF_DEEP_352", "TF_DEEP_352_D2A"),
    ),
    ("TS_HAND_INNER", "testsuite", "Hand inner", ()),
    ("TC_HAND_INNER", "testcase", "Hand inner case", ()),
}

DEEP_DOC = {"buildername": "needs", "srcdir": "doc_test/nested_deep"}


@pytest.mark.parametrize("test_app", [DEEP_DOC], indirect=True)
def test_the_expansion_mints_in_pre_order(test_app):
    """The order the docs state: a suite, then its direct cases (in report order, also one
    written after a nested suite), then its nested suites the same way. ``needs.json`` is
    sorted by id, so the order is read off the page's need nodes."""
    from sphinx_needs.nodes import Need

    app = test_app
    app.build()

    order = [node["refid"] for node in app.env.get_doctree("index").findall(Need)]
    assert order == [
        "TF_DEEP",
        "TF_DEEP_B14",
        "TF_DEEP_B14_9851F",
        "TF_DEEP_B14_DC6D6",
        "TF_DEEP_B14_F23",
        "TF_DEEP_B14_F23_3455F",
        "TF_DEEP_B14_F23_1C856",
        "TF_DEEP_B14_F23_D2A",
        "TF_DEEP_B14_F23_D2A_51668",
        "TF_DEEP_B14_F23_D2A_A5614",
        "TF_DEEP_B14_DBE",
        "TF_DEEP_B14_DBE_6E55A",
        "TF_DEEP_352",
        "TF_DEEP_352_011FC",
        "TF_DEEP_352_D2A",
        "TF_DEEP_352_D2A_C63AD",
        "TS_HAND_INNER",
        "TC_HAND_INNER",
        "REQ_1",
    ]
    assert _rows(_needs(app), "index") == DEEP_NEEDS


@pytest.mark.parametrize("test_app", [DEEP_DOC], indirect=True)
def test_a_hand_written_case_finds_the_first_suite_of_the_name_in_pre_order(test_app):
    """``inner`` is nested at depth 2 under ``outer > mid`` and at depth 1 under the LATER
    ``second``: pre-order finds the depth-2 one first (a breadth-first search would find
    ``second > inner``, which has no ``test_i1``)."""
    app = test_app
    app.build()

    needs = _needs(app)
    assert needs["TS_HAND_INNER"]["cases"] == 2
    assert needs["TC_HAND_INNER"]["case"] == "test_i1"
    assert needs["TC_HAND_INNER"]["classname"] == "pkg.Inner"


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/nested_lookup"}],
    indirect=True,
)
def test_a_name_twice_at_the_top_level_finds_the_first(test_app):
    """A merged report holds ``<testsuite name="pytest">`` twice: ``:suite: pytest`` is the
    first, two cases, not the second's three."""
    app = test_app
    app.build()

    assert _needs(app)["TS_MERGED"]["cases"] == 2


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/nested_twins",
            "warning": io.StringIO(),
        }
    ],
    indirect=True,
)
def test_two_suites_of_one_name_under_one_parent_still_raise(test_app):
    """Their auto-suite ids collide, as they do for top-level suites. Since #2052 that is
    a ``test_reports.duplicate_id`` warning, not a raised ``Exception``: the first twin is
    expanded, the second -- and its case -- is not."""
    test_app.build()

    assert (
        "index.rst:4: WARNING: Suite ID TF_TWINS_B14_BE6 already exists by twin (twin): "
        "the report holds two suites named twin; only the first is expanded"
    ) in test_app._warning.getvalue()
    assert sorted(_needs(test_app)) == ["TF_TWINS", "TF_TWINS_B14", "TF_TWINS_B14_BE6"]
