from pathlib import Path

import pytest

from sphinxcontrib.needs.api.need import NeedsTagNotAllowed


@pytest.mark.parametrize("create_app", [{"buildername": "html", "srcdir": "doc_test/broken_tags"}], indirect=True)
def test_doc_build_html(create_app):
    with pytest.raises(NeedsTagNotAllowed):
        app = create_app
        app.build()
        html = Path(app.outdir, "index.html").read_text()
        assert "<h1>BROKEN DOCUMENT" in html
        assert "SP_TOO_003" in html


@pytest.mark.parametrize("create_app", [{"buildername": "html", "srcdir": "doc_test/broken_tags_2"}], indirect=True)
def test_doc_build_html_unneeded_chars(create_app):
    """
    Test for https://github.com/useblocks/sphinxcontrib-needs/issues/36
    ; at the end of tags needs to be removed #36
    """
    app = create_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "<h1>BROKEN DOCUMENT" in html
    assert "SP_TOO_004" in html
    assert ":needs_tag:" not in html
    assert "``" not in html
