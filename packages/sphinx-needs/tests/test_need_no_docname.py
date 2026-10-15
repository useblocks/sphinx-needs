import re
from pathlib import Path

import pytest

from sphinx_needs_testkit import assert_no_warnings


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_need_no_docname",
            "plantuml": True,
        }
    ],
    indirect=True,
)
def test_need_without_docname_in_diagrams(test_app):
    """A need with neither a document nor an external url is drawn without a link.

    ``add_need`` takes ``docname=None``. A needflow or needuml drawing such a need used
    to end the build with an ``UnboundLocalError`` (``calculate_link`` never bound its
    link), and an empty link is no better: PlantUML refuses ``[[]]`` as a syntax error,
    which surfaces as a build warning. So the build renders both diagrams warning-free.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert html.count("<object data=") == 2  # both diagrams rendered
    # `ref()` with no url falls back to its label: `[[ labelled]]` would parse, but as a
    # link whose target is the label text
    svgs = "".join(
        p.read_text(encoding="utf8") for p in Path(app.outdir).rglob("*.svg")
    )
    assert "labelled" in svgs
    assert 'href="labelled"' not in svgs
    assert "status_of_nodoc" in svgs  # the `option=` form reads the need's field


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_need_no_docname_roles"}],
    indirect=True,
)
def test_need_without_docname_in_roles(test_app):
    """Roles and needtable show a need with no document unlinked, and still link others.

    ``:need:``, ``:need_outgoing:`` and ``:need_incoming:`` took a need that is not
    in a document to be external, and asserted its ``external_url``; needtable made a
    reference with no target, which the HTML writer refuses. Either ended the build
    (#2244). A need's layout renders the outgoing and incoming roles for its links and
    backlinks rows, so linking to such a need was enough.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    # needs_show_link_title is on, so each shows the title, not only the id
    nodoc_text = "Need without a document (R_NODOC)"
    external_link = 'href="https://example.com/R_EXT.html"'
    for label, expect_external in (("REF", False), ("OUT", True), ("IN", True)):
        match = re.search(rf"<p>{label}: (.*?)</p>", html, re.DOTALL)
        assert match, f"no {label} paragraph"
        rendered = match.group(1)
        assert nodoc_text in rendered, (label, rendered)
        # shown as text: the only link is the external need's
        assert rendered.count("<a ") == int(expect_external), (label, rendered)
        assert (external_link in rendered) is expect_external, (label, rendered)

    rows = {
        m.group(1): m.group(0)
        for m in re.finditer(
            r'<tr class="need[^"]*" data-need-id="(\w+)">.*?</tr>', html, re.DOTALL
        )
    }
    # its id cell, and its entry in another need's links columns, are text
    assert '<td class="needs_id"><p>R_NODOC</p></td>' in rows["R_NODOC"]
    assert ">R_NODOC</a>" not in rows["R_DOC"]
    assert "R_NODOC</p>" in rows["R_DOC"]
    assert external_link in rows["R_DOC"]
