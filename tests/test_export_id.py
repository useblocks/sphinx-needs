try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from sphinx_testing import with_app


@with_app(buildername='needs', srcdir='doc_test/doc_export_id')
def test_export_id(app, status, warning):
    app.build()
    html = Path(app.outdir, 'needs.json').read_text()
    assert 'TEST_001' in html


