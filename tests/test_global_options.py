from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "create_app", [{"buildername": "html", "srcdir": "doc_test/doc_global_options"}], indirect=True
)
def test_doc_global_option(create_app):
    app = create_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()

    assert "global_1" in html
    assert "global_2" in html
    assert "global_3" in html
    assert "global_4" in html
    assert "global_5" in html

    assert "test_global" in html
    assert "1.27" in html
    assert "Test output of need GLOBAL_ID" in html

    assert "STATUS_IMPL" in html
    assert "STATUS_UNKNOWN" in html
    assert "STATUS_CLOSED" not in html
