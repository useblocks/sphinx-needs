from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/parallel_doc", "parallel": 4}], indirect=True
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert app.statuscode == 0
    assert "<h1>PARALLEL TEST DOCUMENT" in html
    assert "SP_TOO_001" in html
