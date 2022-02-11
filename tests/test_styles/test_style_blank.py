from pathlib import Path

import pytest
from sphinx.builders.html import StandaloneHTMLBuilder


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_style_blank"}], indirect=True)
def test_doc_style_blank(test_app):
    # css_files is not cleared between test runs so css files get
    # progressively added.  This forces it to clear before re-building
    if hasattr(StandaloneHTMLBuilder, "css_files"):
        del StandaloneHTMLBuilder.css_files[:]

    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "blank.css" in html
    assert "modern.css" not in html
    assert "UNKNOWN.css" not in html
