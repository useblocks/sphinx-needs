from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_style_custom"}],
    indirect=True,
)
def test_doc_style_custom(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "blank.css" not in html
    assert "modern.css" not in html
    assert "UNKNOWN.css" not in html
    assert "custom.css" in html

    css = Path(app.outdir, "_static/sphinx-needs/my_custom.css").read_text()
    assert "background-color: black;" in css
