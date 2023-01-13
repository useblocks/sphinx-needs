from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_list2need"}], indirect=True)
def test_doc_list2need_html(test_app):
    app = test_app
    app.build()
    index_html = Path(app.outdir, "index.html").read_text()
    assert "NEED-002" in index_html
    assert "Sub-Need on level 3" in index_html
    assert '<a class="reference internal" href="#test"><span class="std std-ref">Test chapter</span></a>' in index_html

    # Check parent-child linking (nested)
    assert (
        '<span class="parent_needs"><span><a class="reference internal" href="#NEED-002" title="NEED-003">NEED-002</a></span></span>'
        in index_html
    )
