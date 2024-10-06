import os
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needreport", "no_plantuml": True}],
    indirect=True,
)
def test_doc_needarch(test_app):
    app = test_app
    app.build()
    # check for warning about missing options
    warnings = (
        strip_colors(test_app._warning.getvalue())
        .replace(str(test_app.srcdir) + os.path.sep, "<srcdir>/")
        .strip()
    ).splitlines()
    assert warnings == [
        "<srcdir>/index.rst:6: WARNING: No options specified to generate need report [needs.needreport]",
        "<srcdir>/index.rst:8: WARNING: Could not load needs report template file <srcdir>/unknown.rst [needs.needreport]",
    ]

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "Need Types" in html
    assert "Need Extra Links" in html
    assert "Need Extra Options" in html
    assert "Need Metrics" in html
