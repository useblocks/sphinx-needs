"""The need directives refuse with a located, typed warning and an error box (#2052, #2115).

``test-file``, ``test-suite`` and ``test-case`` used to stop the build on every option
they refused (a ``SphinxError`` subclass, or a bare ``Exception`` for ``:collapse:``), on a
duplicate id their own ``:auto_suites:`` / ``:auto_cases:`` expansion minted (a bare
``Exception`` naming no cause), and whenever sphinx-needs refused their need
(``InvalidNeedException``, which they did not catch). Each of these is now a
``test_reports.*`` warning located on the directive; an option or sphinx-needs refusal
leaves an error box where the need would have been, and a duplicate expansion id keeps the
FIRST need and skips the later one (a suite with its cases and nested suites).

#2115: a ``tr_extra_options`` name with an upper-case letter could never be written on a
directive, since docutils lowercases option names before looking them up.

The ``[test_reports.<subtype>]`` suffix is not asserted (Sphinx < 8 does not print it);
``suppress_warnings`` naming the subtype is what pins the type. Reports are written as bytes.
"""

import hashlib
import io
import re
from pathlib import Path

import pytest
from docutils import nodes

from sphinx_needs.data import SphinxNeedsData
from sphinx_test_reports.exceptions import InvalidConfigurationError

UTILS = Path(__file__).parent / "doc_test" / "utils"
GOOD = (
    b'<testsuite name="S" tests="1">'
    b'<testcase classname="C" name="c" time="0.1"/>'
    b"</testsuite>"
)
#: Two different cases whose legacy ids share one ``tr_case_id_length = 1`` slice (the
#: first hex digit of SHA1("Ct3") and SHA1("Ct7") is ``2``).
SLICE = (
    b'<testsuite name="S" tests="2">'
    b'<testcase classname="C" name="t3"/><testcase classname="C" name="t7"/>'
    b"</testsuite>"
)
#: Lets the short ids below and the lower-case deterministic ids through sphinx-needs.
ANY_ID = 'needs_id_regex = ".*"\n'
DETERMINISTIC = ANY_ID + "tr_deterministic_case_ids = True\n"


def _hex(text: str, length: int) -> str:
    return hashlib.sha1(text.encode("UTF-8")).hexdigest().upper()[:length]


def _fixture(name: str) -> bytes:
    return (UTILS / name).read_bytes()


def _error_boxes(app) -> list[str]:
    return [box.astext() for box in app.env.get_doctree("index").findall(nodes.error)]


def _needs(app) -> dict:
    return dict(SphinxNeedsData(app.env).get_needs_view())


def _of_type(app, need_type: str) -> list[str]:
    return sorted(i for i, need in _needs(app).items() if need["type"] == need_type)


def _src(app, name: str) -> str:
    return str(Path(app.srcdir, name))


# --- N1, N3: option refusals ---------------------------------------------------------------


def test_an_invalid_collapse_is_a_warning_and_a_box(build_page):
    """N1. Master: ``Exception: collapse attribute must be true or false`` (rc 2)."""
    app, stream = build_page(
        ".. test-file:: F\n   :id: TF_COL\n   :file: good.xml\n   :collapse: maybe\n",
        files={"good.xml": GOOD},
    )

    message = "collapse attribute must be true or false"
    assert app.statuscode == 0
    assert f"index.rst:4: WARNING: {message}" in stream
    assert stream.count("WARNING:") == 1
    assert _error_boxes(app) == [message]
    assert "TF_COL" not in _needs(app)


#: N3: (rst, need id, subtype, message with ``{path}`` for the report's resolved path).
OPTION_ROWS = {
    "suite-not-found": (
        ".. test-suite:: X\n   :id: TS_NOPE\n   :file: good.xml\n   :suite: NoSuch\n",
        "TS_NOPE",
        "suite_not_found",
        "Suite NoSuch not found in test file {path}",
    ),
    "case-suite-not-found": (
        ".. test-case:: X\n   :id: TC_NOPE\n   :file: good.xml\n   :suite: NoSuch\n"
        "   :case: c\n",
        "TC_NOPE",
        "suite_not_found",
        "Suite NoSuch not found in test file {path}",
    ),
    "case-not-found": (
        ".. test-case:: X\n   :id: TC_NOPE\n   :file: good.xml\n   :suite: S\n"
        "   :case: NoSuch\n",
        "TC_NOPE",
        "case_not_found",
        "Case NoSuch with classname None not found in test file {path} and testsuite S",
    ),
    "suite-without-suite": (
        ".. test-suite:: X\n   :id: TS_NOPE\n   :file: good.xml\n",
        "TS_NOPE",
        "option_missing",
        "Suite not given!",
    ),
    "case-without-case": (
        ".. test-case:: X\n   :id: TC_NOPE\n   :file: good.xml\n   :suite: S\n",
        "TC_NOPE",
        "option_missing",
        "Case or classname not given!",
    ),
    "file-without-file": (
        ".. test-file:: X\n   :id: TF_NOPE\n",
        "TF_NOPE",
        "option_missing",
        "Option test_file must be set.",
    ),
}


@pytest.mark.parametrize("row", OPTION_ROWS)
def test_an_option_refusal_is_a_warning_and_a_box(build_page, row):
    """N3. Master: a ``SphinxError`` -- ``TestReportInvalidOptionError: Suite NoSuch not
    found in test file …`` and its siblings, ``TestReportFileNotSetError`` -- ended the
    build. The texts are kept word for word."""
    rst, need_id, _, template = OPTION_ROWS[row]
    app, stream = build_page(rst, files={"good.xml": GOOD})

    message = template.format(path=_src(app, "good.xml"))
    assert app.statuscode == 0
    assert f"index.rst:4: WARNING: {message}" in stream
    assert stream.count("WARNING:") == 1
    assert _error_boxes(app) == [message]
    assert need_id not in _needs(app)


@pytest.mark.parametrize(
    "row",
    ["suite-not-found", "case-not-found", "file-without-file", "case-without-case"],
)
def test_the_option_refusals_are_typed(build_page, row):
    rst, _, subtype, _ = OPTION_ROWS[row]
    _, stream = build_page(
        rst,
        files={"good.xml": GOOD},
        confoverrides={"suppress_warnings": [f"test_reports.{subtype}"]},
    )

    assert stream == ""


def test_the_collapse_refusal_is_typed(build_page):
    _, stream = build_page(
        ".. test-file:: F\n   :id: TF_COL\n   :file: good.xml\n   :collapse: maybe\n",
        files={"good.xml": GOOD},
        confoverrides={"suppress_warnings": ["test_reports.option_invalid"]},
    )

    assert stream == ""


# --- N2: :auto_cases: alone ------------------------------------------------------------------


def test_auto_cases_without_auto_suites_keeps_the_file_need(build_page):
    """N2. Master: ``TestReportIncompleteConfigurationError: option auto_cases must be used
    together with auto_suites for test-file directives.`` propagated (rc 2) -- after the
    file's need had been added."""
    app, stream = build_page(
        ".. test-file:: F\n   :id: TF_AC\n   :file: good.xml\n   :auto_cases:\n",
        files={"good.xml": GOOD},
    )

    assert app.statuscode == 0
    assert (
        "index.rst:4: WARNING: option auto_cases must be used together with auto_suites "
        "for test-file directives." in stream
    )
    assert stream.count("WARNING:") == 1
    assert _of_type(app, "testfile") == ["TF_AC"]
    assert _of_type(app, "testsuite") == []
    assert _of_type(app, "testcase") == []
    assert _error_boxes(app) == []


def test_the_auto_cases_warning_is_typed(build_page):
    _, stream = build_page(
        ".. test-file:: F\n   :id: TF_AC\n   :file: good.xml\n   :auto_cases:\n",
        files={"good.xml": GOOD},
        confoverrides={"suppress_warnings": ["test_reports.option_invalid"]},
    )

    assert stream == ""


# --- N4-N6: duplicate ids of one expansion ---------------------------------------------------

MANY = ".. test-file:: F\n   :id: TF_MANY\n   :file: many.xml\n   :auto_suites:\n"


def test_two_suite_names_in_one_slice_keep_the_first(build_page):
    """N4. Master: ``Exception: Suite ID TF_MANY_8D8 already exists by
    vfc_hash_TFixedMap/1 (vfc_hash_TVector234/0)`` (rc 2)."""
    app, stream = build_page(
        MANY,
        files={"many.xml": _fixture("many_testsuites.xml")},
        conf="tr_suite_id_length = 3\n",
    )

    assert app.statuscode == 0
    assert stream.count("WARNING:") == 1
    assert (
        "index.rst:4: WARNING: Suite ID TF_MANY_8D8 already exists by "
        "vfc_hash_TFixedMap/1 (vfc_hash_TVector234/0); raise tr_suite_id_length"
    ) in stream
    needs = _needs(app)
    assert needs["TF_MANY_8D8"]["title"] == "vfc_hash_TFixedMap/1"
    titles = {need["title"] for need in needs.values()}
    assert "vfc_hash_TVector234/0" not in titles
    # 53 suites, one collision at three hex digits (counted independently of the code).
    prefixes = [
        _hex(suite, 3)
        for suite in re.findall(
            r'<testsuite name="([^"]*)"', _fixture("many_testsuites.xml").decode()
        )
    ]
    assert len(prefixes) == 53
    assert len(_of_type(app, "testsuite")) == len(set(prefixes)) == 52
    assert _error_boxes(app) == []


def test_the_duplicate_id_warning_is_typed(build_page):
    _, stream = build_page(
        MANY,
        files={"many.xml": _fixture("many_testsuites.xml")},
        conf="tr_suite_id_length = 3\n",
        confoverrides={"suppress_warnings": ["test_reports.duplicate_id"]},
    )

    assert stream == ""


def test_two_suites_of_one_name_keep_the_first_and_its_cases(build_page):
    """N5. Master: ``Exception: Suite ID TF_X_02A already exists by S (S)``."""
    app, stream = build_page(
        ".. test-file:: F\n   :id: TF_DUP\n   :file: d.xml\n   :auto_suites:\n"
        "   :auto_cases:\n",
        files={"d.xml": _fixture("dup_suites.xml")},
    )

    suite_id = "TF_DUP_" + _hex("S", 3)
    assert app.statuscode == 0
    assert stream.count("WARNING:") == 1
    assert (
        f"index.rst:4: WARNING: Suite ID {suite_id} already exists by S (S): the report "
        "holds two suites named S; only the first is expanded"
    ) in stream
    assert _of_type(app, "testsuite") == [suite_id]
    # The first suite's case is minted; the second suite's is not.
    assert _of_type(app, "testcase") == [f"{suite_id}_{_hex('Ca', 5)}"]


def test_one_case_twice_in_a_suite_keeps_the_first(build_page):
    """N6. Master: ``Exception: Case ID exists: TF_D_02A_E4AF3``."""
    app, stream = build_page(
        ".. test-file:: F\n   :id: TF_DC\n   :file: d.xml\n   :auto_suites:\n"
        "   :auto_cases:\n",
        files={"d.xml": _fixture("dup_cases.xml")},
    )

    case_id = f"TF_DC_{_hex('S', 3)}_{_hex('Ct', 5)}"
    assert app.statuscode == 0
    assert stream.count("WARNING:") == 1
    assert (
        f"index.rst:4: WARNING: Case ID exists: {case_id}: the report holds the case C.t "
        "twice; only the first is expanded"
    ) in stream
    assert _of_type(app, "testcase") == [case_id]


CROSS = ".. test-file:: F\n   :id: TF_CS\n   :file: c.xml\n   :auto_suites:\n   :auto_cases:\n"


def test_one_case_in_two_suites_under_deterministic_ids_keeps_the_first(build_page):
    """N6. One registry per EXPANSION: the per-suite list could not see the second suite's
    case. Master: ``InvalidNeedException: A need with ID 'testcase__C__t_lmgdl' already
    exists. [duplicate_id]`` (rc 2)."""
    app, stream = build_page(
        CROSS, files={"c.xml": _fixture("cross_suite_cases.xml")}, conf=DETERMINISTIC
    )

    assert app.statuscode == 0
    assert stream.count("WARNING:") == 1
    assert (
        "index.rst:4: WARNING: Case ID exists: testcase__C__t_lmgdl: the report holds "
        "the case C.t twice; only the first is expanded"
    ) in stream
    assert _of_type(app, "testcase") == ["testcase__C__t_lmgdl"]


def test_one_case_in_two_suites_under_legacy_ids_is_two_needs(build_page):
    """N6, the control: the suite's id is part of a legacy case id."""
    app, stream = build_page(
        CROSS, files={"c.xml": _fixture("cross_suite_cases.xml")}, conf=ANY_ID
    )

    assert stream == ""
    assert len(_of_type(app, "testcase")) == 2


def test_two_cases_in_one_slice_name_the_lengths(build_page):
    """N6. Two DIFFERENT cases whose legacy ids share a ``tr_case_id_length`` slice."""
    app, stream = build_page(
        ".. test-file:: F\n   :id: TF_SL\n   :file: s.xml\n   :auto_suites:\n"
        "   :auto_cases:\n",
        files={"s.xml": SLICE},
        conf="tr_case_id_length = 1\n",
    )

    case_id = f"TF_SL_{_hex('S', 3)}_2"
    assert stream.count("WARNING:") == 1
    assert (
        f"index.rst:4: WARNING: Case ID exists: {case_id}; raise tr_case_id_length, or "
        "switch tr_deterministic_case_ids on"
    ) in stream
    assert _of_type(app, "testcase") == [case_id]


# --- N7: sphinx-needs refuses the need -------------------------------------------------------

AUTO = ".. test-file:: F\n   :id: TF_GT\n   :file: g.xml\n   :auto_suites:\n   :auto_cases:\n"
HAND = (
    "\n.. test-case:: hand\n   :file: g.xml\n   :suite: MathTest\n   :case: Addition\n"
)
ADDITION = "testcase__MathTest__Addition_hcuyy"


def test_a_generated_id_another_need_holds_says_to_author_one(build_page):
    """N7. Master: ``InvalidNeedException: A need with ID 'testcase__MathTest__Addition_hcuyy'
    already exists. [duplicate_id]`` (rc 2)."""
    app, stream = build_page(
        AUTO + HAND, files={"g.xml": _fixture("gtest_data.xml")}, conf=DETERMINISTIC
    )

    message = (
        f"A need with ID '{ADDITION}' already exists. [duplicate_id]; "
        "give the directive an :id: of its own"
    )
    assert app.statuscode == 0
    assert stream.count("WARNING:") == 1
    assert f"index.rst:10: WARNING: {message}" in stream
    assert _error_boxes(app) == [message]
    assert _needs(app)[ADDITION]["title"] == "Addition"


def test_an_authored_id_another_need_holds_is_reported_plainly(build_page):
    app, stream = build_page(
        AUTO + HAND + f"   :id: {ADDITION}\n",
        files={"g.xml": _fixture("gtest_data.xml")},
        conf=DETERMINISTIC,
    )

    message = f"A need with ID '{ADDITION}' already exists. [duplicate_id]"
    assert stream.count("WARNING:") == 1
    assert f"index.rst:10: WARNING: {message}" in stream
    assert "give the directive" not in stream
    assert _error_boxes(app) == [message]
    assert _needs(app)[ADDITION]["title"] == "Addition"


def test_a_need_holding_an_expansion_id_first_keeps_it(build_page):
    """N7. Document order decides who warns: the LATER claimant, here the expansion."""
    suite_id = "TF_GT_" + _hex("MathTest", 3)
    app, stream = build_page(
        f".. req:: holds the id\n   :id: {suite_id}\n\n" + AUTO,
        files={"g.xml": _fixture("gtest_data.xml")},
        conf=ANY_ID,
    )

    message = f"A need with ID '{suite_id}' already exists. [duplicate_id]"
    assert app.statuscode == 0
    assert stream.count("WARNING:") == 1
    assert f"index.rst:7: WARNING: {message}" in stream
    assert "give the directive" not in stream
    assert _needs(app)[suite_id]["title"] == "holds the id"


def test_the_need_refusal_is_typed(build_page):
    _, stream = build_page(
        AUTO + HAND,
        files={"g.xml": _fixture("gtest_data.xml")},
        conf=DETERMINISTIC,
        confoverrides={"suppress_warnings": ["test_reports.need"]},
    )

    assert stream == ""


# --- N8: tr_extra_options names are matched case-insensitively (#2115) -----------------------

OWNER = 'tr_extra_options = ["Owner"]\nneeds_fields = {"Owner": {"nullable": True}}\n'


@pytest.mark.parametrize("spelling", ["Owner", "owner"])
def test_a_capitalised_extra_option_can_be_written_on_a_directive(
    make_app, tmp_path, clean_docutils_registry, spelling
):
    """N8. Master: ``ERROR: Error in "test-file" directive: unknown option: "owner".``
    for both spellings -- docutils lowercases the name, the spec held ``Owner``."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(
        'extensions = ["sphinx_needs", "sphinx_test_reports"]\n' + OWNER,
        encoding="utf-8",
    )
    (src / "index.rst").write_text(
        "Probe\n=====\n\n.. test-file:: F\n   :id: TF_OWN\n   :file: g.xml\n"
        f"   :auto_suites:\n   :{spelling}: qa-team\n",
        encoding="utf-8",
    )
    (src / "g.xml").write_bytes(_fixture("gtest_data.xml"))
    status, warning = io.StringIO(), io.StringIO()
    app = make_app("html", srcdir=src, status=status, warning=warning, freshenv=True)
    app.build()

    assert warning.getvalue() == ""
    needs = _needs(app)
    assert needs["TF_OWN"]["Owner"] == "qa-team"
    # The JUnit property route is unchanged: MathTest's `Owner="platform-team"`
    # attribute still lands in the field (the control).
    assert needs["TF_OWN_" + _hex("MathTest", 3)]["Owner"] == "platform-team"
    assert (
        "tr_extra_options: write 'Owner' on a directive as :owner:" in status.getvalue()
    )


def test_two_extra_options_equal_but_for_case_are_refused(make_app, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(
        'extensions = ["sphinx_needs", "sphinx_test_reports"]\n'
        'tr_extra_options = ["Owner", "owner"]\n'
        'needs_fields = {"Owner": {"nullable": True}, "owner": {"nullable": True}}\n',
        encoding="utf-8",
    )
    (src / "index.rst").write_text("Probe\n=====\n", encoding="utf-8")

    with pytest.raises(InvalidConfigurationError, match="'Owner' and 'owner'"):
        make_app("html", srcdir=src, freshenv=True)
