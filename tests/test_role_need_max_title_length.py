import os
from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/doc_role_need_max_title_length_unlimited')
def test_max_title_length_unlimited(app, status, warning):

    os.environ["MAX_TITLE_LENGTH"] = "-1"
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert "ROLE NEED TEMPLATE" in html
    assert '[SP_TOO_001] Command line interface (implemented) Specification/spec - test;test2 - SP_TOO_002 -  - ' \
           'The Tool awesome shall have a command line interface.' in html


@with_app(buildername='html', srcdir='doc_test/doc_role_need_max_title_length')
def test_max_title_length_10(app, status, warning):

    os.environ["MAX_TITLE_LENGTH"] = "10"
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert "ROLE NEED TEMPLATE" in html
    assert '[SP_TOO_001] Command... (implemented) Specification/spec - test;test2 - SP_TOO_002 -  - ' \
           'The Tool awesome shall have a command line interface.' in html
