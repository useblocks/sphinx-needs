from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_need_delete"}],
    indirect=True,
)
def test_doc_need_delete(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()

    assert "First Req Need" in html
    assert "Not Implemented" in html
    assert "DELID123" in html
    assert "DELID126" not in html
    assert "Second Spec Need" not in html
    assert "Nested Implemented Need" not in html
