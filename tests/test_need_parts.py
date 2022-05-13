from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_need_parts"}], indirect=True)
def test_doc_need_parts(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert (
        '<span class="need-part" id="SP_TOO_001.1">exit()<a class="needs-id reference internal" '
        'href="#SP_TOO_001.1"> 1</a></span>' in html
    )

    assert '<em class="xref need">exit() (SP_TOO_001.1)</em>' in html
    assert '<em class="xref need">start() (SP_TOO_001.2)</em>' in html
    assert '<em class="xref need">blub() (SP_TOO_001.awesome_id)</em>' in html
    assert '<em class="xref need">My custom link name (SP_TOO_001.awesome_id)</em>' in html
    assert "SP_TOO_001" in html
