from pathlib import Path

import pytest

from sphinxcontrib.needs.api.need import NeedsTagNotAllowed


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/broken_tags")])
def test_doc_build_html(create_app, buildername):
    with pytest.raises(NeedsTagNotAllowed):
        make_app = create_app[0]
        srcdir = create_app[1]
        app = make_app(buildername, srcdir=srcdir)

        app.build()
        html = Path(app.outdir, "index.html").read_text()
        assert "<h1>BROKEN DOCUMENT" in html
        assert "SP_TOO_003" in html


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/broken_tags_2")])
def test_doc_build_html_unneeded_chars(create_app, buildername):
    """
    Test for https://github.com/useblocks/sphinxcontrib-needs/issues/36
    ; at the end of tags needs to be removed #36
    """
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "<h1>BROKEN DOCUMENT" in html
    assert "SP_TOO_004" in html
    assert ":needs_tag:" not in html
    assert "``" not in html
