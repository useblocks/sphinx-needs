from pathlib import Path

from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/doc_style_unknown')
def test_doc_style_unknown(app, status, warning):
    # css_files is not cleared between test runs so css files get
    # progressively added.  This forces it to clear before re-building
    if hasattr(StandaloneHTMLBuilder, 'css_files'):
        del StandaloneHTMLBuilder.css_files[:]
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert 'blank.css' in html
    assert 'modern.css' not in html
    assert 'UNKNOWN.css' not in html
