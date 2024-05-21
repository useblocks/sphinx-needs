from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_style_modern"}],
    indirect=True,
)
def test_doc_style_modern(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "blank.css" not in html
    assert "modern.css" in html
