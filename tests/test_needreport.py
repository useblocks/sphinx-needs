from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needreport"}],
    indirect=True,
)
def test_doc_needarch(test_app):
    app = test_app
    app.build()
    # check for warning about missing options
    warnings = app._warning.getvalue()
    assert (
        "index.rst:6: WARNING: No options specified to generate need report [needs.report]"
        in warnings
    )
    assert "index.rst:8: WARNING: Could not load needs report template file" in warnings
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "Need Types" in html
    assert "Need Extra Links" in html
    assert "Need Extra Options" in html
    assert "Need Metrics" in html
