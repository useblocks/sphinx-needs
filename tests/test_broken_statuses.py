import pytest

from sphinxcontrib.needs.api.need import NeedsStatusNotAllowed


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/broken_statuses")])
def test_doc_build_html(create_app, buildername):
    with pytest.raises(NeedsStatusNotAllowed):
        make_app = create_app[0]
        srcdir = create_app[1]
        app = make_app(buildername, srcdir=srcdir)

        app.build()
        html = (app.outdir / "index.html").read_text()
        assert "<h1>BROKEN DOCUMENT" in html
        assert "SP_TOO_002" in html
