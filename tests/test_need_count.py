from pathlib import Path

import pytest


@pytest.mark.parametrize("create_app", [{"buildername": "html", "srcdir": "doc_test/doc_need_count"}], indirect=True)
def test_doc_need_count(create_app):
    app = create_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "result_1-3" in html
    assert "result_2-2" in html
    assert "result_3-4" in html
