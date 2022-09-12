from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/custom_types"}],
    indirect=True,
)
def test_custom_types_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir / "index.html").read_text()
    assert "Test-Path" in html
    assert "Test-Container" in html
    assert "Test-Run" in html
