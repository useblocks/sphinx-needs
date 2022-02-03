from pathlib import Path

import pytest


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/generic_doc")])
def test_doc_build_html(create_app, buildername):
    # app.builder.build_all()
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "<h1>TEST DOCUMENT" in html
    assert "SP_TOO_001" in html
