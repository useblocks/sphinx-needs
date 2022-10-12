from pathlib import Path

import pytest
from docutils import __version__ as doc_ver


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needflow"}], indirect=True)
def test_doc_build_html(test_app):
    import sphinx

    if sphinx.__version__.startswith("3.5"):
        return

    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SPEC_1" in html
    assert "SPEC_2" in html
    assert "STORY_1" in html
    assert "STORY_2" in html

    if int(doc_ver.split(".")[1]) >= 18:
        assert '<figure class="align-center" id="needflow-index-0">' in html
    else:
        assert '<div class="figure align-center" id="needflow-index-0">' in html


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needflow_incl_child_needs"}], indirect=True
)
def test_doc_build_needflow_incl_child_needs(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert html
    assert "STORY_2" in html
    assert "SPEC_1" in html
