from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/import_doc')  # , warningiserror=True)
def test_import_json(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert 'TEST IMPORT TITLE' in html
    assert 'TEST_01' in html
    assert 'TEST_TEST_01' in html
    assert 'new_tag' in html

    # Check filters
    filter_html = (app.outdir / 'filter.html').read_text()
    assert "TEST_01" not in filter_html
    assert "TEST_02" in filter_html

    # search() test
    assert "AAA" in filter_html

