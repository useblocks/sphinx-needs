from pathlib import Path

import pytest
from sphinx import version_info
from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_style_unknown",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_style_unknown(test_app):
    # css_files is not cleared between test runs so css files get
    # progressively added.  This forces it to clear before re-building
    if version_info >= (7, 2):
        # TODO changed in sphinx 7.2
        if hasattr(StandaloneHTMLBuilder, "_css_files"):
            del StandaloneHTMLBuilder._css_files[:]
    elif hasattr(StandaloneHTMLBuilder, "css_files"):
        del StandaloneHTMLBuilder.css_files[:]

    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).splitlines()
    assert warnings == [
        "WARNING: needs_css not an existing file: UNKNOWN.css [needs.config]"
    ]

    html = Path(app.outdir, "index.html").read_text()
    assert "modern.css" not in html
    assert "UNKNOWN.css" not in html
