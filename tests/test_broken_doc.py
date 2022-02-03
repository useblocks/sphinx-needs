import pytest

from sphinxcontrib.needs.api.need import NeedsDuplicatedId


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/broken_doc")])
def test_doc_build_html(create_app, buildername):
    with pytest.raises(NeedsDuplicatedId):
        make_app = create_app[0]
        srcdir = create_app[1]
        app = make_app(buildername, srcdir=srcdir)

        app.build()
        html = (app.outdir / "index.html").read_text()
        assert "<h1>BROKEN DOCUMENT" in html
        assert "SP_TOO_001" in html
