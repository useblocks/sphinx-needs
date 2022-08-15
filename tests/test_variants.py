from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/variant_doc"}], indirect=True)
def test_variant_options_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "No ID" in html
    assert "progress" in html
    assert "extension" in html

    assert "Test story" in html
    assert "ST_001" in html
    assert "Daniel Woste" in html
    assert "Randy Duodu" not in html

    assert "Custom Variant" in html
    assert "CV_0002" in html
    assert "open" in html
    assert "start" in html
    assert "commence" in html
