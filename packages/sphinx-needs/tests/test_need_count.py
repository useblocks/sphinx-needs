from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_need_count"}],
    indirect=True,
)
def test_doc_need_count(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "result_1-3" in html
    assert "result_2-2" in html
    assert "result_3-4" in html
    assert "result_4-1" in html
    assert "result_5-inf" in html
