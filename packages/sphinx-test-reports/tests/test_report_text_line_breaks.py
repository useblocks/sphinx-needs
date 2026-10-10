"""A test case's message, text and captured output stay inside their literal blocks.

``test-case`` writes a failed case's ``<failure>`` message, its text and its
``<system-out>`` into the need's content as indented reStructuredText literal blocks
(``**Message**::``, ``**Text**::``, ``**System-out**::``). docutils reads that source line
by line, and its lines end at more than ``\\n``: a carriage return (alone or before a
``\\n``), VT, FF, FS, GS, RS, NEL, LINE SEPARATOR and PARAGRAPH SEPARATOR end one too
(``str.splitlines``). Text split only on ``\\n`` and indented piece by piece left the part
after any of those at column 0, where it ended the literal block ("Literal block ends
without a blank line") and was read as reStructuredText: a directive written there was
run. Every row here holds one such character followed by a ``raw`` directive at column 0
and a marker element; the marker must be shown as text inside the block, never as an
element.

``line_breaks.xml`` carries the five characters an XML report can (CR, CR+LF, NEL, LINE
SEPARATOR, PARAGRAPH SEPARATOR); XML 1.0 does not allow VT, FF, FS, GS or RS even as
character references, so ``line_breaks.json`` carries all ten through the JSON reader. One
case per character, one ``test-case`` per case. CR+LF never escaped (each line's trailing
CR is dropped before the parse): its rows are the control.
"""

import io
import re
import shutil
from pathlib import Path

import pytest
from docutils.parsers.rst import directives, roles
from sphinx.testing.util import SphinxTestApp
from sphinx.util.docutils import additional_nodes, unregister_node

UTILS = Path(__file__).parent / "doc_test" / "utils"
XML_BOUNDARIES = ["CR", "CRLF", "NEL", "LS", "PS"]
ALL_BOUNDARIES = ["CR", "CRLF", "VT", "FF", "FS", "GS", "RS", "NEL", "LS", "PS"]
#: The three blocks: the marker prefix each block's text carries, by block.
BLOCKS = {"message": "MSG", "text": "TXT", "system-out": "OUT"}


def _build(tmp_path_factory, report: str) -> tuple[str, str]:
    """Build a page holding one ``test-case`` over ``report``; return (html, warnings)."""
    # As `clean_docutils_registry` does: start from docutils' own registries.
    directives._directives.clear()
    roles._roles.clear()
    for node in list(additional_nodes):
        unregister_node(node)
        additional_nodes.discard(node)
    src = tmp_path_factory.mktemp("line_breaks") / "src"
    src.mkdir()
    (src / "conf.py").write_text(
        'extensions = ["sphinx_needs", "sphinx_test_reports"]\n', encoding="utf-8"
    )
    # One `test-case` per character, so no row can carry another row's marker.
    boundaries = XML_BOUNDARIES if report.endswith(".xml") else ALL_BOUNDARIES
    (src / "index.rst").write_text(
        "Probe\n=====\n\n"
        + "".join(
            f".. test-case:: T {name}\n   :id: TC_LB_{name}\n"
            f"   :file: {report}\n   :suite: S\n   :case: t_{name}\n\n"
            for name in boundaries
        ),
        encoding="utf-8",
    )
    shutil.copy(UTILS / report, src / report)
    warning = io.StringIO()
    app = SphinxTestApp("html", srcdir=src, warning=warning, freshenv=True)
    try:
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    finally:
        app.cleanup()
    return html, warning.getvalue()


@pytest.fixture(scope="module")
def xml_page(tmp_path_factory):
    return _build(tmp_path_factory, "line_breaks.xml")


@pytest.fixture(scope="module")
def json_page(tmp_path_factory):
    return _build(tmp_path_factory, "line_breaks.json")


def _assert_kept_in_a_literal_block(html: str, marker: str) -> None:
    """The marker is TEXT inside a ``<pre>`` (as ``<b>marker</b>``, escaped), and the page
    holds no ``<b>`` element of it. Sphinx highlights a literal block, so the ``<pre>``'s
    text is read with its highlighting tags removed."""
    preformatted = [
        re.sub(r"<[^>]+>", "", block)
        for block in re.findall(r"<pre>(.*?)</pre>", html, re.DOTALL)
    ]
    assert any(f"&lt;b&gt;{marker}&lt;/b&gt;" in block for block in preformatted), (
        f"{marker} not in a <pre>"
    )
    assert f"<b>{marker}</b>" not in html, f"{marker} is an element"


@pytest.mark.parametrize("boundary", XML_BOUNDARIES)
@pytest.mark.parametrize("block", BLOCKS)
def test_an_xml_report_s_text_stays_in_its_block(xml_page, block, boundary):
    html, _ = xml_page
    _assert_kept_in_a_literal_block(html, f"M_{BLOCKS[block]}_{boundary}")


@pytest.mark.parametrize("boundary", ALL_BOUNDARIES)
@pytest.mark.parametrize("block", BLOCKS)
def test_a_json_report_s_text_stays_in_its_block(json_page, block, boundary):
    html, _ = json_page
    _assert_kept_in_a_literal_block(html, f"M_{BLOCKS[block]}_{boundary}")


@pytest.mark.parametrize("page", ["xml_page", "json_page", "imported_page"])
def test_no_literal_block_ends_early(request, page):
    _, warnings = request.getfixturevalue(page)
    assert "Literal block ends without a blank line" not in warnings


@pytest.fixture(scope="module")
def imported_page(tmp_path_factory):
    """``line_breaks.xml`` through the converter, its ``needs.json`` through ``needimport``."""
    from ub_test_reports.cli import main

    directives._directives.clear()
    roles._roles.clear()
    for node in list(additional_nodes):
        unregister_node(node)
        additional_nodes.discard(node)
    src = tmp_path_factory.mktemp("line_breaks_import") / "src"
    src.mkdir()
    code = main(
        [
            "build",
            "needs",
            str(UTILS / "line_breaks.xml"),
            "--output",
            str(src / "needs.json"),
            "--no-config",
        ]
    )
    assert code == 0
    (src / "conf.py").write_text(
        'extensions = ["sphinx_needs", "sphinx_test_reports"]\n'
        # the converter's ids are lower-case; sphinx-needs' default regex is not
        'needs_id_regex = "^[A-Za-z0-9_]{5,}"\n',
        encoding="utf-8",
    )
    (src / "index.rst").write_text(
        "Imported\n========\n\n.. needimport:: needs.json\n", encoding="utf-8"
    )
    warning = io.StringIO()
    app = SphinxTestApp("html", srcdir=src, warning=warning, freshenv=True)
    try:
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    finally:
        app.cleanup()
    return html, warning.getvalue()


@pytest.mark.parametrize("boundary", XML_BOUNDARIES)
@pytest.mark.parametrize("block", BLOCKS)
def test_an_imported_need_s_text_stays_in_its_block(imported_page, block, boundary):
    """The converter writes the same blocks into ``needs.json``; ``needimport`` parses
    them as reStructuredText too."""
    html, _ = imported_page
    _assert_kept_in_a_literal_block(html, f"M_{BLOCKS[block]}_{boundary}")
