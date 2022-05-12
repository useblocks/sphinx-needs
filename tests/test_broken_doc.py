import pytest

from sphinx_needs.api.need import NeedsDuplicatedId


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/broken_doc"}], indirect=True)
def test_doc_build_html(test_app):
    with pytest.raises(NeedsDuplicatedId):
        app = test_app

        app.build()
        html = (app.outdir / "index.html").read_text()
        assert "<h1>BROKEN DOCUMENT" in html
        assert "SP_TOO_001" in html
