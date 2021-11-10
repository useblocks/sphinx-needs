from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/basic_doc")
def test_doc_build_html(app, status, warning):
    app.build()
    html = (app.outdir / "index.html").read_text()
    assert "<h1>Basic Document" in html
    assert "ASuccessfulTest" in html
