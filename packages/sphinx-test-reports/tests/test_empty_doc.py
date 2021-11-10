from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/empty_doc")
def test_doc_build_html(app, status, warning):
    app.build()
    html = (app.outdir / "index.html").read_text()
    assert "<h1>Empty Document" in html
