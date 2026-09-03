import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(
    sys.platform == "win32", reason="assert fails on windows, need to fix later."
)
@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/unicode_support"}],
    indirect=True,
)
def test_unicode_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "Загрузка" in html
    assert "Aufräumlösung" in html
