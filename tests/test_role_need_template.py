from sphinx_testing import with_app
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path
    

@with_app(buildername='html', srcdir='doc_test/doc_role_need_template')
def test_doc_build_html(app, status, warning):

    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert "ROLE NEED TEMPLATE" in html
    assert '[SP_TOO_001] Command line interface (implemented) Specification/spec - test;test2 - SP_TOO_002 -  - ' \
           'The Tool awesome shall have a command line interface.' in html

