from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/custom_types')
def test_custom_types_html(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert 'Test-Path' in html
    assert 'Test-Container' in html
    assert 'Test-Run' in html
