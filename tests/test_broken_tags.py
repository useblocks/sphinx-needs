from nose.tools import raises

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from sphinx_testing import with_app

from sphinxcontrib.needs.directives.need import NeedsTagNotAllowed


@raises(NeedsTagNotAllowed)
@with_app(buildername='html', srcdir='doc_test/broken_tags')
def test_doc_build_html(app, status, warning):
    app.build()
    html = Path(app.outdir,  'index.html').read_text()
    assert '<h1>BROKEN DOCUMENT' in html
    assert 'SP_TOO_003' in html


@with_app(buildername='html', srcdir='doc_test/broken_tags_2')
def test_doc_build_html_unneeded_chars(app, status, warning):
    """
    Test for https://github.com/useblocks/sphinxcontrib-needs/issues/36
    ; at the end of tags needs to be removed #36
    """
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert '<h1>BROKEN DOCUMENT' in html
    assert 'SP_TOO_004' in html
    assert ':needs_tag:' not in html
    assert '``' not in html