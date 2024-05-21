from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_style_blank"}],
    indirect=True,
)
def test_doc_style_blank(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "blank.css" in html
    assert "modern.css" not in html
    assert "UNKNOWN.css" not in html
