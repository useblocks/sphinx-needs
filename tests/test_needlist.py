from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/doc_needlist')
def test_doc_build_html(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert 'SP_TOO_001' in html
    assert 'id="needlist-index-0"' in html
