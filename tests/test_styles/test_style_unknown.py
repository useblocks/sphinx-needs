from pathlib import Path

import pytest
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
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).splitlines()
    assert warnings == [
        "WARNING: needs_css not an existing file: UNKNOWN.css [needs.config]"
    ]

    html = Path(app.outdir, "index.html").read_text()
    assert "modern.css" not in html
    assert "UNKNOWN.css" not in html
