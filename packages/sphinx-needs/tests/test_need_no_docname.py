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
    """``:need:``, ``:need_outgoing:`` and ``:need_incoming:`` show such a need unlinked.

    Each role took a need that is not external, or has no document, to be an external
    one, and asserted its ``external_url`` -- ending the build (#2244). The need's
    layout renders the same two link roles for its links and backlinks rows.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    for label, text in (
        ("REF", "Need without a document (R_NODOC)"),
        ("OUT", "R_NODOC"),
        ("IN", "R_NODOC"),
    ):
        match = re.search(rf"<p>{label}: (.*?)</p>", html, re.DOTALL)
        assert match, f"no {label} paragraph"
        rendered = match.group(1)
        assert text in rendered, (label, rendered)
        # shown as text: no link to a document, and none to an empty url
        assert "<a " not in rendered, (label, rendered)
