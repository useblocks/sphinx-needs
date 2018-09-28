import re
from sphinx_testing import with_app
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


@with_app(buildername='html', srcdir='doc_test/doc_global_options')
def test_doc_global_option(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()

    assert 'global_1' in html
    assert 'global_2' in html
    assert 'global_3' in html

    assert 'test_global' in html
    assert '1.27' in html
    assert 'Test output of need GLOBAL_ID' in html
