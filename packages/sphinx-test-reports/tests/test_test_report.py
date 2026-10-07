"""``test-report`` with the shipped default template, in a user project.

The directive renders its template and inserts the result as rST, so three of the
values it fills in are shapes, not just strings: the body (#2051), the report path
(#2051) and, through the template itself, what a user's build is asked to include
(#1932).
"""

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

PROJECT = "doc_test/test_report_user_project"
#: The three reports' ``:file:``, exactly as written in the project.
AS_WRITTEN = "../utils/xml_data.xml"


def _needs_json(app) -> dict:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs", "srcdir": PROJECT}], indirect=True
)
def test_the_body_is_the_generated_test_file_content(test_app):
    """The body lands inside the generated ``test-file``, line for line.

    It was formatted into the template as the ``repr`` of docutils' ``StringList``,
    ``"['First content line.', 'Second content line.']"`` -- and a plain newline join
    would put the second line at column 0, ending the ``test-file`` directive the
    template indents it under.
    """
    app = test_app
    app.build()
    needs = _needs_json(app)
    assert needs["REP_ROOT"]["content"] == "First content line.\nSecond content line."
    assert needs["REP_SUB"]["content"] == "Only line."
    assert needs["REP_EMPTY"]["content"] == ""


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": PROJECT}], indirect=True
)
def test_the_body_renders_inside_the_test_file_card(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    card = BeautifulSoup(html, "html.parser").find("table", id="REP_ROOT")
    assert card is not None
    content = card.find("td", class_="content")
    assert content is not None
    # both lines, and nothing else: not the list's repr, and not a second line that
    # left the card because it ended the test-file directive
    assert " ".join(content.get_text().split()) == (
        "First content line. Second content line."
    )


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs", "srcdir": PROJECT}], indirect=True
)
def test_the_report_path_is_recorded_as_written(test_app):
    """The generated ``test-file`` records ``:file:`` as written, as a hand-written one does.

    It used to be handed the RESOLVED, absolute path, so the report-path field of a
    ``test-report``'s file, suites and cases differed from every other test-file's --
    and from one machine to the next. Written as given, it is resolved against
    ``tr_rootdir`` exactly as the ``test-report`` itself resolved it, so a report in a
    subdirectory document still finds the same file.
    """
    app = test_app
    app.build()
    needs = _needs_json(app)
    for report in ("REP_ROOT", "REP_SUB", "REP_EMPTY"):
        family = {k: v for k, v in needs.items() if k.startswith(report)}
        # the file, its one suite and xml_data.xml's three cases: the report was found
        assert sorted(v["type"] for v in family.values()) == [
            "testcase",
            "testcase",
            "testcase",
            "testfile",
            "testsuite",
        ], report
        for need_id, need in family.items():
            assert need["file"] == AS_WRITTEN, need_id
    assert needs["REP_SUB"]["docname"] == "sub/page"


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": PROJECT}], indirect=True
)
def test_the_default_template_builds_cleanly_in_a_user_project(test_app):
    """No warning, and no empty *Template* section (#1932).

    The shipped template ended with a *Template* section that ``literalinclude``\\ d
    the template itself, by a path relative to the including document -- one only this
    package's own docs could resolve. Every user's ``test-report`` warned
    ``Include file ... not found`` (so ``-W`` failed) and published a *Template*
    heading with nothing under it. The warning stream captured here is what ``-W``
    turns into errors.
    """
    app = test_app
    app.build()
    warnings = app._warning.getvalue()
    assert "Include file" not in warnings
    assert warnings == ""
    for page in ("index.html", "sub/page.html"):
        html = Path(app.outdir, page).read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        headings = [h.get_text(strip=True).rstrip("¶") for h in soup.find_all("h2")]
        assert "Template" not in headings, (page, headings)
        assert soup.find(id="template") is None, page


CUSTOM = "doc_test/test_report_custom_rootdir"


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs", "srcdir": CUSTOM}], indirect=True
)
def test_a_custom_template_and_rootdir(test_app):
    """A template whose test-file sits at ONE space, and a ``tr_rootdir`` set elsewhere.

    The body's further lines take the indentation the template gives ``{content}``,
    whatever it is -- so the generated content equals a hand-written test-file's with
    the same body. And ``{file}`` is ``:file:`` as written (``xml_data.xml``), not a path
    made relative to some other directory: the generated test-file resolves it against
    ``tr_rootdir`` as the test-report did.
    """
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""
    needs = _needs_json(app)
    assert needs["REP_ONE"]["content"] == needs["TF_ORACLE"]["content"]
    assert needs["REP_ONE"]["content"] == "First line.\nSecond line."
    family = {k: v for k, v in needs.items() if k.startswith("REP_ONE")}
    assert sorted(v["type"] for v in family.values()) == [
        "testcase",
        "testcase",
        "testcase",
        "testfile",
        "testsuite",
    ]
    for need_id, need in family.items():
        assert need["file"] == "xml_data.xml", need_id
    assert needs["TF_ORACLE"]["file"] == "xml_data.xml"
