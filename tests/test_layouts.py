import sys

import sphinx
from sphinx_testing import with_app

from tests.util import extract_needs_from_html


@with_app(buildername="html", srcdir="doc_test/doc_layout")
def test_doc_build_html(app, status, warning):

    # Somehow the xml-tree in extract_needs_from_html() works not correctly with py37 and specific
    # extracts, which are needed for sphinx >3.0 only.
    # Everything with Py3.8 is fine again and also Py3.7 with sphinx<3 works here.
    if (
        sys.version_info[0] == 3
        and sys.version_info[1] == 7
        and sphinx.version_info[0] >= 3
    ):
        return True

    app.build()
    html = (app.outdir / "index.html").read_text()
    assert "title_clean_layout" in html
    assert "title_complete_layout" in html
    assert "title_focus_layout" not in html
    assert "title_example_layout" in html

    needs = extract_needs_from_html(html)
    assert len(needs) == 4

    assert '<tr class="footer row-even"><td class="footer_left" colspan="2">' in html
