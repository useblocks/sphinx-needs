from pathlib import Path

import pytest

from tests.conftest import warnings


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_style_unknown",
        }
    ],
    indirect=True,
)
def test_doc_style_unknown(test_app):
    app = test_app
    app.build()

    warning_records = warnings(app)
    assert warning_records == [
        "WARNING: needs_css not an existing file: UNKNOWN.css [needs.config]"
    ]

    html = Path(app.outdir, "index.html").read_text()
    assert "modern.css" not in html
    assert "UNKNOWN.css" not in html
