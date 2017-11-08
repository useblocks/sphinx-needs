from sphinx_testing import with_app
from nose.tools import raises
from sphinxcontrib.need import NeedsStatusNotAllowed


@raises(NeedsStatusNotAllowed)
@with_app(buildername='html', srcdir='doc_test/broken_statuses')
def test_doc_build_html(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert '<h1>BROKEN DOCUMENT' in html
    assert 'SP_TOO_002' in html
