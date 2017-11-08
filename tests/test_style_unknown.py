from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/doc_style_unknown')
def test_doc_style_unknown(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert 'blank.css' in html
    assert 'modern.css' not in html
    assert 'UNKNOWN.css' not in html
