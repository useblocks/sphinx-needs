from sphinx_testing import with_app
from nose.tools import raises
from sphinxcontrib.need import NeedsDuplicatedId


@with_app(buildername='html', srcdir='doc_test/broken_syntax_doc')
def test_doc_broken_syntax(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
