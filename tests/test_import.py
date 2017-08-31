from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/import_doc')  # , warningiserror=True)
def test_import_json(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert 'TEST IMPORT TITLE' in html

    assert 'TEST_01' in html

    assert 'TEST_TEST_01' in html
