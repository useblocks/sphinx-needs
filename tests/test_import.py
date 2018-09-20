try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/import_doc')  # , warningiserror=True)
def test_import_json(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert 'TEST IMPORT TITLE' in html
    assert 'TEST_01' in html
    assert 'test_TEST_01' in html
    assert 'new_tag' in html

    # Check filters
    filter_html = Path(app.outdir, 'filter.html').read_text()
    assert "TEST_01" not in filter_html
    assert "TEST_02" in filter_html

    # search() test
    assert "AAA" in filter_html

