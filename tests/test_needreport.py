from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needreport"}], indirect=True)
def test_doc_needarch(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "Need Types" in html
    assert "Need Extra Links" in html
    assert "Need Extra Options" in html
    assert "Need Metrics" in html
