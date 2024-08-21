import os

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/broken_doc", "no_plantuml": True}],
    indirect=True,
)
def test_doc_build_html(test_app: SphinxTestApp):
    test_app.build()
    warnings = (
        strip_colors(test_app._warning.getvalue())
        .replace(str(test_app.srcdir) + os.path.sep, "<srcdir>/")
        .strip()
    )
    assert (
        warnings
        == "<srcdir>/index.rst:11: WARNING: A need with ID SP_TOO_001 already exists, title: 'Command line interface'. [needs.duplicate_id]"
    )
    html = (test_app.outdir / "index.html").read_text()
    assert "<h1>BROKEN DOCUMENT" in html
    assert "SP_TOO_001" in html
