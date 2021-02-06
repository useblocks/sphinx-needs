# -*- coding: utf-8 -*-

from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/doc_needflow')
def test_doc_build_html(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert 'SPEC_1' in html
    assert 'SPEC_2' in html
    assert 'STORY_1' in html
    assert 'STORY_2' in html
