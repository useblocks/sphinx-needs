from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/doc_style_modern')
def test_doc_style_modern(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert 'blank.css' not in html
    assert 'modern.css' in html
