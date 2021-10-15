from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needs_external_needs")
def test_doc_build_html(app, status, warning):
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "EXT_TEST_01" in html
    assert "EXT_TEST_02" in html
    assert "EXT_TEST_03" in html
