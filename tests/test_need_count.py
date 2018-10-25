from sphinx_testing import with_app
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


@with_app(buildername='html', srcdir='doc_test/doc_need_count')
def test_doc_need_count(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert 'result_1-3' in html
    assert 'result_2-2' in html
    assert 'result_3-4' in html
