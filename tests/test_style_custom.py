from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/doc_style_custom')
def test_doc_style_custom(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert 'blank.css' not in html
    assert 'modern.css' not in html
    assert 'UNKNOWN.css' not in html
    assert 'custom.css' in html

    css = (app.outdir / '_static/sphinx-needs/my_custom.css').read_text()
    assert 'background-color: black;' in css
