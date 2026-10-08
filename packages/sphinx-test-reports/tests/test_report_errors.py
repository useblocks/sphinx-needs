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
from docutils.parsers.rst import directives, roles
from sphinx.util.docutils import additional_nodes, unregister_node

from sphinx_needs.data import SphinxNeedsData

CONF = 'extensions = ["sphinx_needs", "sphinx_test_reports"]\n'
#: The page's title; the first directive written after it is on line 4.
TITLE = "Probe\n=====\n\n"

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


@pytest.fixture(autouse=True)
def _a_clean_docutils_registry():
    """Start every build here from docutils' own registries, with nothing of Sphinx's.

    These tests assert EMPTY warning streams. Other modules of this suite build with a
    bare ``Sphinx(...)`` (``test_cli_convert.py``, ``test_project_config.py``), which
    registers Sphinx's directives, roles and node classes with docutils and never takes
    them back; the next app built in the same worker then warns ``directive
    'version-deprecated' is already registered`` / ``node class 'toctree' is already
    registered``, once per name. Emptying the two lookup tables and unregistering the
    nodes is what ``sphinx.util.docutils.docutils_namespace`` undoes when an app is cleaned
    up (docutils loads its own directives and roles back from its static registries on
    first use). Autouse, so it runs before ``test_app`` builds its app too.
    """
    directives._directives.clear()
    roles._roles.clear()
    for node in list(additional_nodes):
        unregister_node(node)
        additional_nodes.discard(node)


def _build(make_app, tmp_path, rst, files=None, confoverrides=None):
    """Build a one-page project and return the app and its warning stream."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(CONF, encoding="utf-8")
    (src / "index.rst").write_text(TITLE + rst, encoding="utf-8")
    for name, data in (files or {}).items():
        (src / name).write_bytes(data)
    warning = io.StringIO()
    app = make_app(
        "html",
        srcdir=src,
        warning=warning,
        confoverrides=confoverrides or {},
        freshenv=True,
    )
    app.build()
    return app, warning.getvalue()


def _error_boxes(app) -> list[str]:
    return [box.astext() for box in app.env.get_doctree("index").findall(nodes.error)]


def _needs(app) -> dict:
    return dict(SphinxNeedsData(app.env).get_needs_view())


def _src(app, name: str) -> str:
    return str(Path(app.srcdir, name))


# --- test-results -----------------------------------------------------------------------


def test_test_results_on_a_missing_report_warns_and_shows_a_box(make_app, tmp_path):
    """R6. Master: ``JUnitFileMissing`` (a ``BaseException``) ended the build, rc 1."""
    app, stream = _build(make_app, tmp_path, ".. test-results:: nope.xml\n")

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
def test_the_missing_report_warning_is_typed(make_app, tmp_path, suppress):
    """R6. Typed, so the subtype AND the bare type silence it (Sphinx's prefix rule)."""
    app, stream = _build(
        make_app,
        tmp_path,
        ".. test-results:: nope.xml\n",
        confoverrides={"suppress_warnings": suppress},
    )

    assert stream == ""
    # Suppressing the warning does not take the box away.
    assert len(_error_boxes(app)) == 1


def test_test_results_on_malformed_xml_warns_and_shows_a_box(make_app, tmp_path):
    """R7. Master: lxml's ``XMLSyntaxError`` ended the build (rc 2)."""
    app, stream = _build(
        make_app, tmp_path, ".. test-results:: bad.xml\n", files={"bad.xml": MALFORMED}
    )

    assert app.statuscode == 0
    path = _src(app, "bad.xml")
    assert f"index.rst:4: WARNING: {path} (line 1, column " in stream
    assert stream.count("WARNING:") == 1
    (box,) = _error_boxes(app)
    assert box.startswith(f"{path} (line 1, column ")


def test_test_results_refuses_a_json_report_by_name(make_app, tmp_path):
    """R7. A ``.json`` argument is refused before parsing: lxml's own message for it,
    ``Start tag expected, '<' not found``, blames the wrong thing."""
    app, stream = _build(
        make_app,
        tmp_path,
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
def test_the_unreadable_report_warning_is_typed(make_app, tmp_path, argument, files):
    """R7. ``test_reports.report_unreadable`` silences both refusals."""
    app, stream = _build(
        make_app,
        tmp_path,
        f".. test-results:: {argument}\n",
        files=files,
        confoverrides={"suppress_warnings": ["test_reports.report_unreadable"]},
    )

    assert stream == ""
    assert len(_error_boxes(app)) == 1


def test_an_option_under_test_results_is_an_unknown_option(make_app, tmp_path):
    """R8, #2138. With no ``option_spec`` and ``final_argument_whitespace``, docutils
    folded ``:class: foo`` into the path (master: ``JUnitFileMissing: … xml_data.xml``
    followed by ``:class: foo`` on the next line). Now docutils refuses the option as
    for any directive, and the path never grows a second line."""
    app, stream = _build(
        make_app,
        tmp_path,
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


def test_the_need_directives_on_a_missing_report_warn_once_each(make_app, tmp_path):
    """R9. Master: ``test-file`` warned (untyped, its location inside the text) and showed
    the box; ``test-suite`` and ``test-case`` crashed on ``None`` (``TypeError: 'NoneType'
    object is not iterable``, rc 2)."""
    app, stream = _build(make_app, tmp_path, NEED_DIRECTIVES.format(report="nope.xml"))

    assert app.statuscode == 0
    message = f"Test file not found: {_src(app, 'nope.xml')}"
    for line in NEED_LINES:
        assert stream.count(f"index.rst:{line}: WARNING: {message}") == 1
    assert stream.count("WARNING:") == 3
    assert _error_boxes(app) == [message] * 3
    assert not set(NEED_IDS) & set(_needs(app))


def test_the_need_directives_on_a_malformed_report_warn_once_each(make_app, tmp_path):
    """R10. Master: ``XMLSyntaxError`` from the first directive ended the build."""
    app, stream = _build(
        make_app,
        tmp_path,
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


def test_the_need_directives_missing_report_warning_is_typed(make_app, tmp_path):
    """R9. One suppression silences all three directives' warnings."""
    _, stream = _build(
        make_app,
        tmp_path,
        NEED_DIRECTIVES.format(report="nope.xml"),
        confoverrides={"suppress_warnings": ["test_reports.report_missing"]},
    )

    assert stream == ""


# --- controls --------------------------------------------------------------------------


def test_a_readable_report_still_builds_quietly(make_app, tmp_path):
    """R11. The control: the same three directives over a good report mint their needs
    and warn about nothing."""
    app, stream = _build(
        make_app,
        tmp_path,
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
def test_basic_doc_builds_with_an_empty_warning_stream(test_app):
    """R11. ``test-results`` over a good report: nothing in the stream."""
    test_app.build()
    assert test_app._warning.getvalue() == ""
