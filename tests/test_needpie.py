# -*- coding: utf-8 -*-

from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needpie")
def test_doc_build_html(app, status, warning):
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SPEC_1" in html
    assert '<img alt="_images/need_pie_' in html
