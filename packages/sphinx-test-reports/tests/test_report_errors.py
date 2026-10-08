"""A report that cannot be read is a located, typed warning and an error box (#2052, #2138).

Every failure a user can cause while a directive READS its report -- the path does not
exist, the file is not well-formed XML, ``test-results`` is handed a JSON file, an option
line under ``test-results`` -- used to end the build with an uncaught exception
(``JUnitFileMissing``, a ``BaseException``; lxml's ``XMLSyntaxError``; ``TypeError`` on
``None`` in ``test-suite`` / ``test-case``) or, for ``test-file`` alone, an untyped and
unlocated warning. Now each one is a warning of the ``test_reports.*`` family, located on
the directive (``index.rst:N:``), the directive puts an error box where its need or table
would have been, and the build goes on.

The ``[test_reports.<subtype>]`` suffix is not asserted anywhere: Sphinx < 8 does not print
it (``show_warning_types`` defaults to off there). The type and subtype are pinned the
other way -- ``suppress_warnings`` naming them empties the stream.

Reports are written to ``tmp_path`` as bytes; pages are read with an explicit encoding.
"""

import io
from pathlib import Path

import pytest
from docutils import nodes

from sphinx_needs.data import SphinxNeedsData

MALFORMED = b"<testsuite><testcase></testsuite>"
GOOD = (
    b'<testsuite name="S" tests="1">'
    b'<testcase classname="C" name="c" time="0.1"/>'
    b"</testsuite>"
)

#: The three need directives, each reading ``{report}``, on lines 4, 8 and 13.
NEED_DIRECTIVES = """\
.. test-file:: F
   :id: TF_ERR
   :file: {report}

.. test-suite:: S
   :id: TS_ERR
   :file: {report}
   :suite: S

.. test-case:: C
   :id: TC_ERR
   :file: {report}
   :suite: S
   :case: c
"""
NEED_LINES = (4, 8, 13)
NEED_IDS = ("TF_ERR", "TS_ERR", "TC_ERR")


def _error_boxes(app) -> list[str]:
    return [box.astext() for box in app.env.get_doctree("index").findall(nodes.error)]


def _needs(app) -> dict:
    return dict(SphinxNeedsData(app.env).get_needs_view())


def _src(app, name: str) -> str:
    return str(Path(app.srcdir, name))


# --- test-results -----------------------------------------------------------------------


def test_test_results_on_a_missing_report_warns_and_shows_a_box(build_page):
    """R6. Master: ``JUnitFileMissing`` (a ``BaseException``) ended the build, rc 1."""
    app, stream = build_page(".. test-results:: nope.xml\n")

    assert app.statuscode == 0
    message = f"Test file not found: {_src(app, 'nope.xml')}"
    assert f"index.rst:4: WARNING: {message}" in stream
    assert stream.count("WARNING:") == 1
    assert _error_boxes(app) == [message]


@pytest.mark.parametrize(
    "suppress",
    [["test_reports.report_missing"], ["test_reports"]],
    ids=["subtype", "type"],
)
def test_the_missing_report_warning_is_typed(build_page, suppress):
    """R6. Typed, so the subtype AND the bare type silence it (Sphinx's prefix rule)."""
    app, stream = build_page(
        ".. test-results:: nope.xml\n",
        confoverrides={"suppress_warnings": suppress},
    )

    assert stream == ""
    # Suppressing the warning does not take the box away.
    assert len(_error_boxes(app)) == 1


def test_test_results_on_malformed_xml_warns_and_shows_a_box(build_page):
    """R7. Master: lxml's ``XMLSyntaxError`` ended the build (rc 2)."""
    app, stream = build_page(
        ".. test-results:: bad.xml\n", files={"bad.xml": MALFORMED}
    )

    assert app.statuscode == 0
    path = _src(app, "bad.xml")
    assert f"index.rst:4: WARNING: {path} (line 1, column " in stream
    assert stream.count("WARNING:") == 1
    (box,) = _error_boxes(app)
    assert box.startswith(f"{path} (line 1, column ")


def test_test_results_refuses_a_json_report_by_name(build_page):
    """R7. A ``.json`` argument is refused before parsing: lxml's own message for it,
    ``Start tag expected, '<' not found``, blames the wrong thing."""
    app, stream = build_page(
        ".. test-results:: report.json\n",
        files={"report.json": b'{"testsuites": []}'},
    )

    message = (
        "test-results reads JUnit XML reports; "
        f"{_src(app, 'report.json')} is a JSON file"
    )
    assert f"index.rst:4: WARNING: {message}" in stream
    assert "Start tag expected" not in stream
    assert _error_boxes(app) == [message]


@pytest.mark.parametrize(
    ("argument", "files"),
    [("bad.xml", {"bad.xml": MALFORMED}), ("report.json", {"report.json": b"{}"})],
    ids=["malformed", "json"],
)
def test_the_unreadable_report_warning_is_typed(build_page, argument, files):
    """R7. ``test_reports.report_unreadable`` silences both refusals."""
    app, stream = build_page(
        f".. test-results:: {argument}\n",
        files=files,
        confoverrides={"suppress_warnings": ["test_reports.report_unreadable"]},
    )

    assert stream == ""
    assert len(_error_boxes(app)) == 1


def test_an_option_under_test_results_is_an_unknown_option(build_page):
    """R8, #2138. With no ``option_spec`` and ``final_argument_whitespace``, docutils
    folded ``:class: foo`` into the path (master: ``JUnitFileMissing: … xml_data.xml``
    followed by ``:class: foo`` on the next line). Now docutils refuses the option as
    for any directive, and the path never grows a second line."""
    app, stream = build_page(
        ".. test-results:: good.xml\n   :class: foo\n",
        files={"good.xml": GOOD},
        confoverrides={"keep_warnings": True},
    )

    assert 'unknown option: "class"' in stream
    assert "Test file not found" not in stream
    # In the page too (kept by `keep_warnings`); its quotes went through smartquotes.
    doctree = app.env.get_doctree("index")
    assert [
        message["level"]
        for message in doctree.findall(nodes.system_message)
        if "unknown option: \N{LEFT DOUBLE QUOTATION MARK}class" in message.astext()
    ] == [3]


# --- the three need directives -----------------------------------------------------------


def test_the_need_directives_on_a_missing_report_warn_once_each(build_page):
    """R9. Master: ``test-file`` warned (untyped, its location inside the text) and showed
    the box; ``test-suite`` and ``test-case`` crashed on ``None`` (``TypeError: 'NoneType'
    object is not iterable``, rc 2)."""
    app, stream = build_page(NEED_DIRECTIVES.format(report="nope.xml"))

    assert app.statuscode == 0
    message = f"Test file not found: {_src(app, 'nope.xml')}"
    for line in NEED_LINES:
        assert stream.count(f"index.rst:{line}: WARNING: {message}") == 1
    assert stream.count("WARNING:") == 3
    assert _error_boxes(app) == [message] * 3
    assert not set(NEED_IDS) & set(_needs(app))


def test_the_need_directives_on_a_malformed_report_warn_once_each(build_page):
    """R10. Master: ``XMLSyntaxError`` from the first directive ended the build."""
    app, stream = build_page(
        NEED_DIRECTIVES.format(report="bad.xml"),
        files={"bad.xml": MALFORMED},
    )

    assert app.statuscode == 0
    prefix = f"{_src(app, 'bad.xml')} (line 1, column "
    for line in NEED_LINES:
        assert stream.count(f"index.rst:{line}: WARNING: {prefix}") == 1
    assert stream.count("WARNING:") == 3
    boxes = _error_boxes(app)
    assert len(boxes) == 3
    assert all(box.startswith(prefix) for box in boxes)
    assert not set(NEED_IDS) & set(_needs(app))


def test_the_need_directives_missing_report_warning_is_typed(build_page):
    """R9. One suppression silences all three directives' warnings."""
    _, stream = build_page(
        NEED_DIRECTIVES.format(report="nope.xml"),
        confoverrides={"suppress_warnings": ["test_reports.report_missing"]},
    )

    assert stream == ""


# --- controls --------------------------------------------------------------------------


def test_a_readable_report_still_builds_quietly(build_page):
    """R11. The control: the same three directives over a good report mint their needs
    and warn about nothing."""
    app, stream = build_page(
        NEED_DIRECTIVES.format(report="good.xml"),
        files={"good.xml": GOOD},
    )

    assert stream == ""
    assert _error_boxes(app) == []
    assert set(NEED_IDS) <= set(_needs(app))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/basic_doc", "warning": io.StringIO()}],
    indirect=True,
)
def test_basic_doc_builds_with_an_empty_warning_stream(
    clean_docutils_registry, test_app
):
    """R11. ``test-results`` over a good report: nothing in the stream."""
    test_app.build()
    assert test_app._warning.getvalue() == ""
