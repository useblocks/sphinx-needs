from nose.tools import raises
from sphinx_testing import with_app
from sphinxcontrib.needs.need import NeedsTagNotAllowed


@raises(NeedsTagNotAllowed)
@with_app(buildername='html', srcdir='doc_test/broken_tags')
def test_doc_build_html(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert '<h1>BROKEN DOCUMENT' in html
    assert 'SP_TOO_003' in html
