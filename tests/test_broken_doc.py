import pytest

from sphinxcontrib.needs.api.need import NeedsDuplicatedId


@pytest.mark.parametrize("create_app", [{"buildername": "html", "srcdir": "doc_test/broken_doc"}], indirect=True)
def test_doc_build_html(create_app):
    with pytest.raises(NeedsDuplicatedId):
        app = create_app

        app.build()
        html = (app.outdir / "index.html").read_text()
        assert "<h1>BROKEN DOCUMENT" in html
        assert "SP_TOO_001" in html
