try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/doc_extra_links')
def test_extra_links(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert 'TEST_001' in html
    assert 'tested by' in html
    assert 'tests' in html
    assert 'blocked by' in html
    assert 'blocks' in html


