from pathlib import Path

import pytest


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/doc_needflow")])
def test_doc_build_html(create_app, buildername):
    import sphinx

    if sphinx.__version__.startswith("3.5"):
        return

    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SPEC_1" in html
    assert "SPEC_2" in html
    assert "STORY_1" in html
    assert "STORY_2" in html
    assert '<figure class="align-center" id="needflow-index-0">' in html
