from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/generic_doc"}], indirect=True)
def test_doc_build_html(test_app):
    # app.builder.build_all()
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "<h1>TEST DOCUMENT" in html
    assert "SP_TOO_001" in html
