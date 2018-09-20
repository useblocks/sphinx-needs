from sphinx_testing import with_app
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path
    

@with_app(buildername='html', srcdir='doc_test/generic_doc')
def test_doc_build_html(app, status, warning):
    #app.builder.build_all()
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert '<h1>TEST DOCUMENT' in html
    assert 'SP_TOO_001' in html
