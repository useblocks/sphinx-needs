"""Where a test need comes from: its hops, and its ``lineno`` (#2209).

Every need a test directive creates records, innermost first, the test's source file (a
test case's ``code`` hop), the report it was read from (the ``report`` hop, with the
element's suite, scope and case) and the page the directive is written on. Its
``lineno`` is the line the directive is written on: for a need a ``test-report``
generates, the ``test-report``'s own line, and after ``rst_prolog`` or in an included
file, the line in the file (#2209). The hops are provisional and reach no
``needs.json``.
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
from pathlib import Path

import pytest

from sphinx_needs.api import NeedSourceHop
from sphinx_needs.data import SphinxNeedsData

#: Four cases, as plain pytest writes them (xunit1): a function, a method, a
#: parameterised one, and one without ``file`` / ``line``.
REPORT = (
    b'<testsuites><testsuite name="pytest" tests="4">'
    b'<testcase classname="tests.test_lines" name="test_plain" '
    b'file="tests/test_lines.py" line="12"/>'
    b'<testcase classname="tests.test_lines.TestKlass" name="test_method" '
    b'file="tests/test_lines.py" line="27"/>'
    b'<testcase classname="tests.test_lines" name="test_stacked[3]" '
    b'file="tests/test_lines.py" line="35"/>'
    b'<testcase classname="tests.test_lines" name="test_nofile"/>'
    b"</testsuite></testsuites>"
)

#: ``index.rst``: each directive on the line its comment-free text gives.
PAGE = """\
Probe
=====

.. test-file:: Plain report
   :file: reports/plain.xml
   :id: TF_PLAIN
   :auto_suites:
   :auto_cases:

Section
-------

.. test-case:: A hand case
   :id: TC_HAND
   :file: reports/plain.xml
   :suite: pytest
   :case: test_method
   :classname: tests.test_lines.TestKlass

.. test-suite:: A hand suite
   :id: TS_HAND
   :file: reports/plain.xml
   :suite: pytest

.. test-report:: Generated report
   :file: reports/plain.xml
   :id: TR_GEN
"""

PROLOG = ".. |a| replace:: A\n.. |b| replace:: B\n.. |c| replace:: C\n"


def _suite_id(parent: str, name: str) -> str:
    return f"{parent}_{hashlib.sha1(name.encode()).hexdigest().upper()[:3]}"


def _case_id(suite_id: str, classname: str, name: str) -> str:
    digest = hashlib.sha1((classname + name).encode()).hexdigest().upper()[:5]
    return f"{suite_id}_{digest}"


def _compact(hop: NeedSourceHop) -> str:
    """One hop on one line: ``kind [document] root:path:start-end (language) ::
    semantic``, as sphinx-needs' own hop snapshots print them (``:start`` alone where
    the hop has no end line)."""
    parts = [hop.kind]
    if hop.document is not None:
        parts.append(f"[{hop.document}]")
    if (physical := hop.physical) is not None:
        where = f"{physical.root}:{physical.path}"
        if physical.start_line is not None:
            where += f":{physical.start_line}"
            if physical.end_line is not None:
                where += f"-{physical.end_line}"
        parts.append(where)
    if hop.language is not None:
        parts.append(f"({hop.language})")
    if hop.origin is not None:
        parts.append(f"origin={hop.origin}")
    if hop.semantic is not None:
        parts.append(
            ":: "
            + " > ".join(
                f"{entry.kind} {entry.name!r}"
                + "".join(f" {key}={value!r}" for key, value in entry.extras)
                for entry in hop.semantic
            )
        )
    return " ".join(parts)


@pytest.fixture
def build(make_app, tmp_path, clean_docutils_registry):
    """Build ``pages`` (name -> text) and ``files`` (name -> bytes) in ``tmp_path/src``;
    return ``(needs view, warnings)``."""

    def run(pages, files, conf=""):
        src = tmp_path / "src"
        for name, text in {
            "conf.py": 'extensions = ["sphinx_needs", "sphinx_test_reports"]\n'
            'needs_id_regex = ".*"\n' + conf,
            **pages,
        }.items():
            (src / name).parent.mkdir(parents=True, exist_ok=True)
            (src / name).write_text(text, encoding="utf-8")
        for name, data in files.items():
            (src / name).parent.mkdir(parents=True, exist_ok=True)
            (src / name).write_bytes(data)
        warning = io.StringIO()
        app = make_app("html", srcdir=src, freshenv=True, warning=warning)
        app.build()
        return SphinxNeedsData(app.env).get_needs_view(), warning.getvalue()

    return run


def _hops(needs, need_id: str) -> list[str]:
    return [_compact(hop) for hop in needs[need_id].source.hops]


SUITE = _suite_id("TF_PLAIN", "pytest")
GEN_SUITE = _suite_id("TR_GEN", "pytest")

#: The hops of every kind of test need, at the page above (PAGE).
EXPECTED_HOPS = {
    "TF_PLAIN": [
        "report srcdir:reports/plain.xml (.xml)",
        "page [index] srcdir:index.rst:4-8 (.rst) :: section 'Probe'",
    ],
    # an auto suite and its cases: the test-file's lines
    SUITE: [
        "report srcdir:reports/plain.xml (.xml) :: suite 'pytest'",
        "page [index] srcdir:index.rst:4-8 (.rst) :: section 'Probe'",
    ],
    _case_id(SUITE, "tests.test_lines", "test_plain"): [
        "code None:tests/test_lines.py:13",
        "report srcdir:reports/plain.xml (.xml) :: suite 'pytest' > "
        "scope 'tests.test_lines' > case 'test_plain'",
        "page [index] srcdir:index.rst:4-8 (.rst) :: section 'Probe'",
    ],
    _case_id(SUITE, "tests.test_lines", "test_stacked[3]"): [
        "code None:tests/test_lines.py:36",
        "report srcdir:reports/plain.xml (.xml) :: suite 'pytest' > "
        "scope 'tests.test_lines' > case 'test_stacked' parameter='3'",
        "page [index] srcdir:index.rst:4-8 (.rst) :: section 'Probe'",
    ],
    # no file in the report: no code hop
    _case_id(SUITE, "tests.test_lines", "test_nofile"): [
        "report srcdir:reports/plain.xml (.xml) :: suite 'pytest' > "
        "scope 'tests.test_lines' > case 'test_nofile'",
        "page [index] srcdir:index.rst:4-8 (.rst) :: section 'Probe'",
    ],
    "TC_HAND": [
        "code None:tests/test_lines.py:28",
        "report srcdir:reports/plain.xml (.xml) :: suite 'pytest' > "
        "scope 'tests.test_lines.TestKlass' > case 'test_method'",
        "page [index] srcdir:index.rst:13-18 (.rst) :: section 'Probe' > section 'Section'",
    ],
    "TS_HAND": [
        "report srcdir:reports/plain.xml (.xml) :: suite 'pytest'",
        "page [index] srcdir:index.rst:20-23 (.rst) :: section 'Probe' > section 'Section'",
    ],
    # what a test-report generates: the page holds no line of the generated text
    "TR_GEN": [
        "report srcdir:reports/plain.xml (.xml)",
        "page [index] srcdir:index.rst (.rst) :: section 'Probe' > section 'Section'",
    ],
    GEN_SUITE: [
        "report srcdir:reports/plain.xml (.xml) :: suite 'pytest'",
        "page [index] srcdir:index.rst (.rst) :: section 'Probe' > section 'Section'",
    ],
    _case_id(GEN_SUITE, "tests.test_lines.TestKlass", "test_method"): [
        "code None:tests/test_lines.py:28",
        "report srcdir:reports/plain.xml (.xml) :: suite 'pytest' > "
        "scope 'tests.test_lines.TestKlass' > case 'test_method'",
        "page [index] srcdir:index.rst (.rst) :: section 'Probe' > section 'Section'",
    ],
}


@pytest.mark.parametrize("need_id", list(EXPECTED_HOPS))
def test_every_kind_of_test_need_records_its_hops(build, need_id):
    needs, warnings = build({"index.rst": PAGE}, {"reports/plain.xml": REPORT})
    assert warnings == ""
    assert _hops(needs, need_id) == EXPECTED_HOPS[need_id]


def test_a_code_hop_has_no_root_no_end_line_and_no_language(build):
    """The test's file is relative to the test run's root, which the build does not
    know; the report gives the test's first line, read by its base (#2381: plain
    pytest's ``27`` is the line above the method), and no last line; it names no
    language."""
    needs, _ = build({"index.rst": PAGE}, {"reports/plain.xml": REPORT})
    code = needs["TC_HAND"].source.hops[0]
    assert code.kind == "code"
    assert needs["TC_HAND"]["case_line"] == "28"
    assert code.physical is not None
    assert (code.physical.root, code.physical.start_line, code.physical.end_line) == (
        None,
        28,
        None,
    )
    assert (code.language, code.origin) == (None, None)


#: The lines each need is written on: a generated need's is its test-report's (#2209).
EXPECTED_LINES = {
    "TF_PLAIN": 4,
    SUITE: 4,
    _case_id(SUITE, "tests.test_lines", "test_plain"): 4,
    "TC_HAND": 13,
    "TS_HAND": 20,
    "TR_GEN": 25,
    GEN_SUITE: 25,
    _case_id(GEN_SUITE, "tests.test_lines", "test_plain"): 25,
}


@pytest.mark.parametrize("prolog", [False, True], ids=["plain", "rst_prolog"])
def test_a_test_need_s_lineno_is_the_line_it_is_written_on(build, prolog):
    """#2209: a need a ``test-report`` generates was at its line in the expanded input
    (``index:44`` and the like); every need was at the parser's line, ``rst_prolog``'s
    lines counted."""
    needs, _ = build(
        {"index.rst": PAGE},
        {"reports/plain.xml": REPORT},
        conf=f"rst_prolog = {PROLOG!r}\n" if prolog else "",
    )
    assert {need_id: needs[need_id]["lineno"] for need_id in EXPECTED_LINES} == (
        EXPECTED_LINES
    )


def test_a_test_need_in_an_included_file_is_at_its_line_there(build):
    """The line in the included file, and the file between the report and the page,
    as a need directive's own."""
    fragment = (
        "Prose in the fragment.\n\n"
        ".. test-file:: Included\n   :file: reports/plain.xml\n   :id: TF_INC\n"
    )
    page = "Probe\n=====\n\nAbove.\n\n.. include:: frag.txt\n"
    needs, warnings = build(
        {"index.rst": page, "frag.txt": fragment}, {"reports/plain.xml": REPORT}
    )
    assert warnings == ""
    assert needs["TF_INC"]["lineno"] == 3
    assert _hops(needs, "TF_INC") == [
        "report srcdir:reports/plain.xml (.xml)",
        "file srcdir:frag.txt:3-5 (.txt)",
        "page [index] srcdir:index.rst (.rst) :: section 'Probe'",
    ]


def test_a_report_outside_the_source_directory_is_a_dotted_path(build, tmp_path):
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "plain.xml").write_bytes(REPORT)
    needs, warnings = build(
        {
            "index.rst": "Probe\n=====\n\n"
            ".. test-file:: Outside\n   :file: ../outside/plain.xml\n   :id: TF_OUT\n"
        },
        {},
    )
    assert warnings == ""
    assert _hops(needs, "TF_OUT")[0] == "report srcdir:../outside/plain.xml (.xml)"


def test_a_need_from_a_json_report_has_a_json_report_hop(build):
    report = (
        b'[{"name": "s1", "tests": 1, "errors": 0, "failures": 0, "skips": 0,'
        b' "passed": 1, "time": 1, "testcase": [{"name": "t1", "classname": "c1",'
        b' "file": "tests/own.py", "result": "passed"}]}]'
    )
    needs, warnings = build(
        {
            "index.rst": "Probe\n=====\n\n"
            ".. test-case:: C\n   :id: TC_JSON\n   :file: r.json\n   :suite: s1\n"
            "   :case: t1\n"
        },
        {"r.json": report},
        conf=JSON_MAPPING.format(extra=""),
    )
    assert warnings == ""
    assert _hops(needs, "TC_JSON") == [
        "code None:tests/own.py",
        "report srcdir:r.json (.json) :: suite 's1' > scope 'c1' > case 't1'",
        "page [index] srcdir:index.rst:4-8 (.rst) :: section 'Probe'",
    ]


JSON_MAPPING = """
tr_json_mapping = {{
    "cfg": {{
        "testsuite": {{
            "name": (["name"], "unknown"), "tests": (["tests"], 0),
            "errors": (["errors"], 0), "failures": (["failures"], 0),
            "skips": (["skips"], 0), "passed": (["passed"], 0),
            "time": (["time"], 0), "testcases": (["testcase"], []),
        }},
        "testcase": {{
            "name": (["name"], "unknown"), "classname": (["classname"], "unknown"),
            "file": (["file"], "unknown"), "line": (["line"], -1),
            "time": (["time"], 0), "result": (["result"], "passed"),
            "type": (["type"], ""), "text": (["text"], ""),
            "message": (["message"], ""), "system-out": (["system-out"], ""),
            {extra}
        }},
    }}
}}
"""


def test_a_report_value_named_like_the_source_file_field_does_not_reach_the_hop(
    build,
):
    """#2411: a ``tr_json_mapping`` key ``case_file`` overrides the need's field today,
    with no warning (that refusal is #2411's own). The code hop is built from the case's
    own ``file``, so the override does not reach it."""
    report = (
        b'[{"name": "s1", "tests": 1, "errors": 0, "failures": 0, "skips": 0,'
        b' "passed": 1, "time": 1, "testcase": [{"name": "t1", "classname": "c1",'
        b' "file": "tests/own.py", "other": "tests/override.py",'
        b' "result": "passed"}]}]'
    )
    needs, _ = build(
        {
            "index.rst": "Probe\n=====\n\n"
            ".. test-case:: C\n   :id: TC_JSON\n   :file: r.json\n   :suite: s1\n"
            "   :case: t1\n"
        },
        {"r.json": report},
        conf=JSON_MAPPING.format(extra='"case_file": (["other"], ""),'),
    )
    assert needs["TC_JSON"]["case_file"] == "tests/override.py"
    assert _hops(needs, "TC_JSON")[0] == "code None:tests/own.py"


def test_no_id_depends_on_a_line(build):
    """No id scheme hashes the line: lines above every directive, and ``rst_prolog``,
    move no id."""
    first, _ = build({"index.rst": PAGE}, {"reports/plain.xml": REPORT})
    ids = set(first)
    moved = PAGE.replace("=====\n\n", "=====\n\nTwo\nlines.\n\n", 1)
    second, _ = build(
        {"index.rst": moved},
        {"reports/plain.xml": REPORT},
        conf=f"rst_prolog = {PROLOG!r}\n",
    )
    assert set(second) == ids


# --- the report's element: nested suites, what a report leaves out ---------------------

#: Two suites named ``inner`` under two parents, each with the case ``k.t1``; a suite
#: with no name, holding a case with no ``classname``; and a case with no ``name``.
NESTED = (
    b'<testsuites><testsuite name="outerA" tests="1">'
    b'<testsuite name="inner" tests="1"><testcase classname="k" name="t1"/></testsuite>'
    b'</testsuite><testsuite name="outerB" tests="1">'
    b'<testsuite name="inner" tests="1"><testcase classname="k" name="t1"/></testsuite>'
    b'</testsuite><testsuite tests="2"><testcase name="t2"/>'
    b'<testcase classname="k"/></testsuite></testsuites>'
)

NESTED_PAGE = """\
Probe
=====

.. test-file:: Nested
   :file: nested.xml
   :id: TF_N
   :auto_suites:
   :auto_cases:

.. test-suite:: The first inner
   :file: nested.xml
   :id: TS_INNER
   :suite: inner

.. test-case:: In the first inner
   :file: nested.xml
   :id: TC_INNER
   :suite: inner
   :case: t1
"""

_A, _B = _suite_id("TF_N", "outerA"), _suite_id("TF_N", "outerB")
_NAMELESS = _suite_id("TF_N", "unknown")

#: The report hop of each need: the suites from the top-level one down, outermost first.
NESTED_REPORT_HOPS = {
    _A: "report srcdir:nested.xml (.xml) :: suite 'outerA'",
    _suite_id(_A, "inner"): "report srcdir:nested.xml (.xml) :: suite 'outerA' > "
    "suite 'inner'",
    _case_id(_suite_id(_A, "inner"), "k", "t1"): "report srcdir:nested.xml (.xml) :: "
    "suite 'outerA' > suite 'inner' > scope 'k' > case 't1'",
    _case_id(_suite_id(_B, "inner"), "k", "t1"): "report srcdir:nested.xml (.xml) :: "
    "suite 'outerB' > suite 'inner' > scope 'k' > case 't1'",
    # a hand suite and case naming ``inner``: the first in pre-order, outerA's
    "TS_INNER": "report srcdir:nested.xml (.xml) :: suite 'outerA' > suite 'inner'",
    "TC_INNER": "report srcdir:nested.xml (.xml) :: suite 'outerA' > suite 'inner' > "
    "scope 'k' > case 't1'",
    # no suite name, no classname: no entry; no case name: the parser's, as given
    _case_id(
        _NAMELESS, "unknown", "t2"
    ): "report srcdir:nested.xml (.xml) :: case 't2'",
    _case_id(
        _NAMELESS, "k", "unknown"
    ): "report srcdir:nested.xml (.xml) :: scope 'k' > case 'unknown'",
    _NAMELESS: "report srcdir:nested.xml (.xml)",
}


@pytest.mark.parametrize("need_id", list(NESTED_REPORT_HOPS))
def test_the_report_hop_names_the_element_s_place_in_the_report(build, need_id):
    """Two cases alike in two suites alike, under two parents, are told apart; what a
    report does not give (the parsers' ``"unknown"``) is no entry, but a case's."""
    needs, warnings = build({"index.rst": NESTED_PAGE}, {"nested.xml": NESTED})
    assert warnings == ""
    assert [hop for hop in _hops(needs, need_id) if hop.startswith("report")] == [
        NESTED_REPORT_HOPS[need_id]
    ]


def test_a_code_hop_s_path_is_posix_and_the_field_as_given(build):
    """A report written on Windows names the test with backslashes: the hop's path is
    POSIX, and the need's ``case_file`` keeps the report's value."""
    report = (
        b'<testsuite name="s" tests="1"><testcase classname="c" name="t" '
        b'file="tests\\sub\\test_w.py" line="3"/></testsuite>'
    )
    needs, warnings = build(
        {
            "index.rst": "Probe\n=====\n\n"
            ".. test-case:: W\n   :id: TC_W\n   :file: w.xml\n   :suite: s\n"
            "   :case: t\n"
        },
        {"w.xml": report},
    )
    assert warnings == ""
    assert needs["TC_W"]["case_file"] == "tests\\sub\\test_w.py"
    assert _hops(needs, "TC_W")[0] == "code None:tests/sub/test_w.py"


def test_a_warning_in_a_test_need_s_content_is_on_its_line(build):
    """The content of a hand ``test-case`` is parsed at its own line: a warning raised
    in it names the line it is on (was the line of the directive's ``:file:``)."""
    page = (
        "Probe\n=====\n\n"  # 1-3
        ".. test-case:: A hand case\n"  # 4
        "   :id: TC_HAND\n"
        "   :file: reports/plain.xml\n"
        "   :suite: pytest\n"
        "   :case: test_method\n"
        "   :classname: tests.test_lines.TestKlass\n"
        "\n"
        "   First line of the content.\n"  # 11
        "\n"
        "   A :nosuchrole:`x` here.\n"  # 13
    )
    _, warnings = build({"index.rst": page}, {"reports/plain.xml": REPORT})
    assert "index.rst:13: ERROR: Unknown interpreted text role" in warnings, warnings


# --- the report hop's path: Sphinx-Needs' rule, computed here ---------------------------

_SRCDIR = os.path.join(os.sep, "project", "docs")

#: ``(srcdir, path)``: what ``physical_for`` and the package's helper are both asked.
PATH_SHAPES = {
    "inside": (_SRCDIR, os.path.join(_SRCDIR, "reports", "r.xml")),
    "outside": (_SRCDIR, os.path.join(os.sep, "project", "reports", "r.xml")),
    "far outside": (_SRCDIR, os.path.join(os.sep, "elsewhere", "r.xml")),
    "relative to the working directory": ("docs", os.path.join("reports", "r.xml")),
    "the source directory itself": (_SRCDIR, _SRCDIR),
    "dotted segments": (_SRCDIR, os.path.join(_SRCDIR, "a", "..", "r.xml")),
}
if sys.platform == "win32":
    PATH_SHAPES["backslashes"] = ("C:\\project\\docs", "C:\\project\\reports\\r.xml")
    PATH_SHAPES["forward slashes"] = ("C:/project/docs", "C:/project/docs/r.xml")
    PATH_SHAPES["another drive"] = ("C:\\project\\docs", "D:\\reports\\r.xml")


@pytest.mark.parametrize("shape", list(PATH_SHAPES))
def test_the_report_path_is_sphinx_needs_rule(shape):
    from sphinx_needs._need_source import physical_for
    from sphinx_test_reports.directives.test_common import _report_physical

    srcdir, path = PATH_SHAPES[shape]
    assert _report_physical(srcdir, path) == physical_for(srcdir, path)


def test_the_report_path_under_a_symlinked_directory_is_sphinx_needs_rule(tmp_path):
    from sphinx_needs._need_source import physical_for
    from sphinx_test_reports.directives.test_common import _report_physical

    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "r.xml").write_bytes(REPORT)
    (tmp_path / "docs").mkdir()
    try:
        (tmp_path / "docs" / "linked").symlink_to(
            tmp_path / "real", target_is_directory=True
        )
    except OSError:
        pytest.skip("no symlinks here")
    for srcdir, path in [
        (tmp_path / "docs", tmp_path / "docs" / "linked" / "r.xml"),
        (tmp_path / "docs" / "linked", tmp_path / "real" / "r.xml"),
    ]:
        assert _report_physical(srcdir, path) == physical_for(srcdir, path)


# --- Google Test's parameters (#2390) ----------------------------------------------

#: googletest 1.17.0's ``--gtest_output=xml`` over ``TEST_P``, ``TYPED_TEST``,
#: ``TYPED_TEST_P`` and ``testing::RegisterTest``: the parameter is in ``value_param`` /
#: ``type_param``, never in the name.
GTEST_PARAMS_XML = (
    Path(__file__).parent / "doc_test" / "utils" / "gtest_params.xml"
).read_bytes()

_LIBCXX_STRING = (
    "std::basic_string<char,std::__1::char_traits<char>,std::__1::allocator<char>>"
)

#: Each case's deterministic id -- the converter's, unchanged by #2390 -- and its
#: ``case_name`` and ``case_parameter``: the value, the type, or both, type first.
GTEST_PARAMS = {
    "testcase__Inst_IntP__Value_0_uhxix": ("Value/0", "1"),
    "testcase__Inst_IntP__Value_1_flspz": ("Value/1", "2"),
    "testcase__S_StrP__Str_0_jeebm": ("Str/0", '"a \\"b\\" <c>"'),
    "testcase__S_StrP__Str_1_lpzaf": ("Str/1", '""'),
    "testcase__PairP__Pair_0_ojtcw": ("Pair/0", "(1, 2)"),
    "testcase__Typed_0__T1_fvlzv": ("T1", "int"),
    "testcase__Typed_1__T1_notmu": ("T1", _LIBCXX_STRING),
    "testcase__My_TP_0__Each_megvw": ("Each", "int"),
    "testcase__My_TP_1__Each_nrkup": ("Each", _LIBCXX_STRING),
    "testcase__DynSuite__Both_riqkf": ("Both", "float, 3.5"),
    # a hand test-case of the RegisterTest case
    "TC_BOTH": ("Both", "float, 3.5"),
}

GTEST_PARAMS_PAGE = """\
Probe
=====

.. test-file:: Parameters
   :file: params.xml
   :id: TF_PARAMS
   :auto_suites:
   :auto_cases:

.. test-case:: Both by hand
   :file: params.xml
   :id: TC_BOTH
   :suite: DynSuite
   :case: Both
"""


def _gtest_params_build(build):
    needs, warnings = build(
        {"index.rst": GTEST_PARAMS_PAGE},
        {"params.xml": GTEST_PARAMS_XML},
        conf="tr_deterministic_case_ids = True\n",
    )
    assert warnings == ""
    return {k: needs[k] for k in needs if needs[k]["type"] == "testcase"}


def test_a_google_test_parameter_moves_no_id(build):
    assert sorted(_gtest_params_build(build)) == sorted(GTEST_PARAMS)


def test_a_google_test_parameter_is_the_case_parameter_and_the_hop_s(build):
    """``case_parameter`` and the report hop's ``parameter`` extra are one value: what
    the name's ``[…]`` gives, else ``value_param``, else ``type_param``, both joined
    type first; ``case_name`` keeps gtest's ``/N``."""
    cases = _gtest_params_build(build)
    got = {}
    for need_id, need in cases.items():
        report = need.source.hops[1]
        assert report.kind == "report"
        assert report.semantic is not None
        case = report.semantic[-1]
        assert case.kind == "case"
        got[need_id] = (
            need["case_name"],
            need["case_parameter"],
            case.name,
            case.extras,
        )
    assert got == {
        need_id: (name, parameter, name, (("parameter", parameter),))
        for need_id, (name, parameter) in GTEST_PARAMS.items()
    }


def test_a_json_mapping_s_unknown_parameter_is_no_parameter(build):
    """A ``tr_json_mapping`` defaulting ``value_param`` / ``type_param`` to
    ``"unknown"``, as the documented example defaults every key: a case without them
    has no parameter, in the field or the hop; one with a value has it (#2390)."""
    report = (
        b'[{"name": "s1", "tests": 2, "errors": 0, "failures": 0, "skips": 0,'
        b' "passed": 2, "time": 1, "testcase": ['
        b'{"name": "t1", "classname": "c1", "result": "passed"},'
        b' {"name": "t2", "classname": "c1", "result": "passed", "value_param": "7"}'
        b"]}]"
    )
    needs, warnings = build(
        {
            "index.rst": "Probe\n=====\n\n"
            ".. test-case:: C1\n   :id: TC_J1\n   :file: r.json\n   :suite: s1\n"
            "   :case: t1\n\n"
            ".. test-case:: C2\n   :id: TC_J2\n   :file: r.json\n   :suite: s1\n"
            "   :case: t2\n"
        },
        {"r.json": report},
        conf=JSON_MAPPING.format(
            extra='"value_param": (["value_param"], "unknown"),'
            ' "type_param": (["type_param"], "unknown"),'
        ),
    )
    assert warnings == ""
    assert needs["TC_J1"]["case_parameter"] is None
    assert needs["TC_J2"]["case_parameter"] == "7"
    assert _hops(needs, "TC_J1")[0] == (
        "report srcdir:r.json (.json) :: suite 's1' > scope 'c1' > case 't1'"
    )
    assert _hops(needs, "TC_J2")[0] == (
        "report srcdir:r.json (.json) :: suite 's1' > scope 'c1' > case 't2'"
        " parameter='7'"
    )


# --- the test's own line: the code hop and ``case_line`` (#2381) -------------------

#: ``REPORT`` as the ub-test-reports plugin writes it: the same cases, counted from 1,
#: and the suite marked so.
MARKED_REPORT = (
    REPORT.replace(
        b'<testsuite name="pytest" tests="4">',
        b'<testsuite name="pytest" tests="4"><properties>'
        b'<property name="ub_test_reports:line_base" value="1"/></properties>',
    )
    .replace(b'line="12"', b'line="13"')
    .replace(b'line="27"', b'line="28"')
    .replace(b'line="35"', b'line="36"')
)

#: A Google Test case (googletest 1.17.0's shape: ``status`` and ``result``), counted
#: from 1, and a case of a producer the reader does not recognise.
OTHER_REPORTS = (
    b'<testsuites name="AllTests"><testsuite name="Suite" tests="1">'
    b'<testcase name="Plain" file="tests/gt_probe.cpp" line="3" status="run" '
    b'result="completed" time="0." classname="Suite"/></testsuite>'
    b'<testsuite name="other" tests="1"><testcase classname="Other" name="t" '
    b'file="src/other.x" line="7"/></testsuite></testsuites>'
)

OTHER_PAGE = """\
Probe
=====

.. test-case:: Google Test
   :id: TC_GTEST
   :file: other.xml
   :suite: Suite
   :case: Plain

.. test-case:: Unknown
   :id: TC_OTHER
   :file: other.xml
   :suite: other
   :case: t
"""


def _code(needs, need_id: str) -> tuple[str | None, str]:
    """A test case's ``case_line`` and its code hop."""
    return needs[need_id]["case_line"], _hops(needs, need_id)[0]


_PLAIN_CASE = _case_id(SUITE, "tests.test_lines", "test_plain")


def test_a_marked_report_gives_its_lines_as_they_are(build):
    needs, warnings = build({"index.rst": PAGE}, {"reports/plain.xml": MARKED_REPORT})
    assert warnings == ""
    assert _code(needs, "TC_HAND") == ("28", "code None:tests/test_lines.py:28")
    assert _code(needs, _PLAIN_CASE) == ("13", "code None:tests/test_lines.py:13")


def test_a_google_test_line_is_the_code_hop_s(build):
    needs, warnings = build({"index.rst": OTHER_PAGE}, {"other.xml": OTHER_REPORTS})
    assert warnings == ""
    assert _code(needs, "TC_GTEST") == ("3", "code None:tests/gt_probe.cpp:3")


def test_the_line_of_an_unrecognised_producer_is_no_hop_s(build):
    """Its base is not known: ``case_line`` is the report's, and the code hop has no
    line, as before."""
    needs, warnings = build({"index.rst": OTHER_PAGE}, {"other.xml": OTHER_REPORTS})
    assert warnings == ""
    assert _code(needs, "TC_OTHER") == ("7", "code None:src/other.x")


def test_line_0_of_a_report_counted_from_1_is_no_hop_s(build):
    report = MARKED_REPORT.replace(b'line="28"', b'line="0"')
    needs, _ = build({"index.rst": PAGE}, {"reports/plain.xml": report})
    assert _code(needs, "TC_HAND") == ("0", "code None:tests/test_lines.py")


def test_tr_line_base_1_reads_an_unmarked_report_from_1(build):
    """The migration for a report that already counts from 1 but carries no mark: one
    written by an earlier version of the plugin, or by S-CORE's ``score_pytest``."""
    needs, warnings = build(
        {"index.rst": PAGE}, {"reports/plain.xml": REPORT}, conf="tr_line_base = 1\n"
    )
    assert warnings == ""
    assert _code(needs, "TC_HAND") == ("27", "code None:tests/test_lines.py:27")


def test_tr_line_base_0_reads_an_unrecognised_producer_from_0(build):
    needs, warnings = build(
        {"index.rst": OTHER_PAGE},
        {"other.xml": OTHER_REPORTS},
        conf="tr_line_base = 0\n",
    )
    assert warnings == ""
    assert _code(needs, "TC_OTHER") == ("8", "code None:src/other.x:8")


def test_a_mark_wins_over_tr_line_base(build):
    needs, warnings = build(
        {"index.rst": PAGE},
        {"reports/plain.xml": MARKED_REPORT},
        conf="tr_line_base = 0\n",
    )
    assert warnings == ""
    assert _code(needs, "TC_HAND") == ("28", "code None:tests/test_lines.py:28")


@pytest.mark.parametrize("value", ["2", "-1", "'one'", "True", "1.0", "None"])
def test_another_tr_line_base_is_refused(
    make_app, tmp_path, clean_docutils_registry, value
):
    from sphinx_test_reports.exceptions import InvalidConfigurationError

    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(
        'extensions = ["sphinx_needs", "sphinx_test_reports"]\n'
        f"tr_line_base = {value}\n",
        encoding="utf-8",
    )
    (src / "index.rst").write_text("Probe\n=====\n", encoding="utf-8")
    with pytest.raises(InvalidConfigurationError, match="tr_line_base"):
        make_app("html", srcdir=src, freshenv=True)


def test_a_json_report_s_line_is_passed_through_and_no_hop_s(build):
    """The rule is the JUnit reader's: a JSON report's line is what its mapping reads,
    passed through, whatever ``tr_line_base`` says, and the code hop has none."""
    report = (
        b'[{"name": "pytest", "tests": 1, "errors": 0, "failures": 0, "skips": 0,'
        b' "passed": 1, "time": 1, "testcase": [{"name": "t1", "classname": "c1",'
        b' "file": "tests/own.py", "line": 12, "result": "passed"}]}]'
    )
    page = (
        "Probe\n=====\n\n"
        ".. test-case:: C\n   :id: TC_JSON\n   :file: r.json\n   :suite: pytest\n"
        "   :case: t1\n"
    )
    for conf in ("", "tr_line_base = 0\n", "tr_line_base = 1\n"):
        needs, _ = build(
            {"index.rst": page},
            {"r.json": report},
            conf=JSON_MAPPING.format(extra="") + conf,
        )
        assert _code(needs, "TC_JSON") == ("12", "code None:tests/own.py"), conf


#: Every id the page and the plain report give, by each id scheme: no id reads a line.
#: (With deterministic ids, the cases the ``test-report`` generates are the ``test-file``'s
#: ids again, and refused as such: the generated suite keeps its own.)
PLAIN_IDS = {
    "legacy": [
        "TC_HAND",
        "TF_PLAIN",
        "TF_PLAIN_0EA",
        "TF_PLAIN_0EA_2E306",
        "TF_PLAIN_0EA_39A69",
        "TF_PLAIN_0EA_49F19",
        "TF_PLAIN_0EA_64266",
        "TR_GEN",
        "TR_GEN_0EA",
        "TR_GEN_0EA_2E306",
        "TR_GEN_0EA_39A69",
        "TR_GEN_0EA_49F19",
        "TR_GEN_0EA_64266",
        "TS_HAND",
    ],
    "deterministic": [
        "TC_HAND",
        "TF_PLAIN",
        "TF_PLAIN_0EA",
        "TR_GEN",
        "TR_GEN_0EA",
        "TS_HAND",
        "testcase__TestKlass__test_method_lbxxb",
        "testcase__test_lines__test_nofile_vhvno",
        "testcase__test_lines__test_plain_whqwm",
        "testcase__test_lines__test_stacked_3__duycp",
    ],
}


@pytest.mark.parametrize("scheme", list(PLAIN_IDS))
def test_no_id_moves_with_the_line_base(build, scheme):
    conf = "tr_deterministic_case_ids = True\n" if scheme == "deterministic" else ""
    needs, _ = build({"index.rst": PAGE}, {"reports/plain.xml": REPORT}, conf=conf)
    assert sorted(needs) == PLAIN_IDS[scheme]
