# -*- coding: utf-8 -*-

from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needflow")
def test_doc_build_html(app, status, warning):
    import sphinx

    if sphinx.__version__.startswith("3.5"):
        return

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SPEC_1" in html
    assert "SPEC_2" in html
    assert "STORY_1" in html
    assert "STORY_2" in html
    assert '<figure class="align-center" id="needflow-index-0">' in html
