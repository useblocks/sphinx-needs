from pathlib import Path

import pytest
from sphinx.builders.html import StandaloneHTMLBuilder


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/doc_style_unknown")])
def test_doc_style_unknown(create_app, buildername):
    # css_files is not cleared between test runs so css files get
    # progressively added.  This forces it to clear before re-building
    if hasattr(StandaloneHTMLBuilder, "css_files"):
        del StandaloneHTMLBuilder.css_files[:]

    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "blank.css" in html
    assert "modern.css" not in html
    assert "UNKNOWN.css" not in html
