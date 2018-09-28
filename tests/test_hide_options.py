import re
from sphinx_testing import with_app
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


@with_app(buildername='html', srcdir='doc_test/doc_hide_options')
def test_doc_hide_options(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()

    assert 'status' not in html
    assert 'tags' not in html
    assert 'test_global' not in html
