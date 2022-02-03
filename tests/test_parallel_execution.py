from pathlib import Path

import pytest


@pytest.mark.parametrize("buildername, srcdir, parallel", [("html", "doc_test/parallel_doc", 4)])
def test_doc_build_html(create_app, buildername, parallel):
    # app.builder.build_all()
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir, parallel=parallel)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert app.statuscode == 0
    assert "<h1>PARALLEL TEST DOCUMENT" in html
    assert "SP_TOO_001" in html
