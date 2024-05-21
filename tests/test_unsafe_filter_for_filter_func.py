from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needs_filter_func_allow_dirty_filter",
        }
    ],
    indirect=True,
)
def test_doc_allow_unsafe_filter_for_filter_func(test_app):
    app = test_app
    app.build()
    index_html = Path(app.outdir, "index.html").read_text()

    assert '<span class="caption-text">Filter func table 001' in index_html
    assert '<td class="needs_title"><p>Feature 001</p></td>' in index_html
    assert '<td class="needs_tcl"><p>10</p></td>' in index_html

    assert '<span class="caption-text">Filter func table 002' in index_html
    assert '<td class="needs_title"><p>Feature 001</p></td>' in index_html
    assert '<td class="needs_tcl"><p>30</p></td>' in index_html
