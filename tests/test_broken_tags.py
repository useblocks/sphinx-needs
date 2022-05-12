from pathlib import Path

import pytest

from sphinx_needs.api.need import NeedsTagNotAllowed


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/broken_tags"}], indirect=True)
def test_doc_build_html(test_app):
    with pytest.raises(NeedsTagNotAllowed):
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text()
        assert "<h1>BROKEN DOCUMENT" in html
        assert "SP_TOO_003" in html


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/broken_tags_2"}], indirect=True)
def test_doc_build_html_unneeded_chars(test_app):
    """
    Test for https://github.com/useblocks/sphinxcontrib-needs/issues/36
    ; at the end of tags needs to be removed #36
    """
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "<h1>BROKEN DOCUMENT" in html
    assert "SP_TOO_004" in html
    assert ":needs_tag:" not in html
    assert "``" not in html
