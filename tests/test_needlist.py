from pathlib import Path

import pytest


@pytest.mark.sphinx(buildername="html", testroot="doc_needlist")
def test_doc_build_html(app, status, warning):
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SP_TOO_001" in html
    assert 'id="needlist-index-0"' in html
