from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_extra_links"}],
    indirect=True,
)
def test_extra_links_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "TEST_001" in html
    assert "tested by" in html
    assert "tests" in html
    assert "blocked by" in html
    assert "blocks" in html

    # Check for correct dead_links handling
    assert '<span class="needs_dead_link">DEAD_LINK_ALLOWED</span>' in html
    assert (
        '<span class="needs_dead_link forbidden">DEAD_LINK_NOT_ALLOWED</span>' in html
    )
    assert '<span class="needs_dead_link forbidden">REQ_005.invalid</span>' in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "latex", "srcdir": "doc_test/doc_extra_links"}],
    indirect=True,
)
def test_extra_links_latex(test_app):
    app = test_app
    app.build()
    tex = Path(app.outdir, "needstestdocs.tex").read_text()
    assert "TEST_001" in tex
    assert "tested by" in tex
    assert "tests" in tex
    assert "blocked by" in tex
    assert "blocks" in tex
