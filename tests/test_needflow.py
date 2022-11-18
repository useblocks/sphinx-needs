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

    index_html = Path(app.outdir, "index.html").read_text()
    assert "SPEC_1 [[../index.html#SPEC_1]]" in index_html
    assert "SPEC_2 [[../index.html#SPEC_2]]" in index_html
    assert "STORY_1 [[../index.html#STORY_1]]" in index_html
    assert "STORY_1.1 [[../index.html#STORY_1.1]]" in index_html
    assert "STORY_1.2 [[../index.html#STORY_1.2]]" in index_html
    assert "STORY_1.subspec [[../index.html#STORY_1.subspec]]" in index_html
    assert "STORY_2 [[../index.html#STORY_2]]" in index_html
    assert "STORY_2.another_one [[../index.html#STORY_2.another_one]]" in index_html

    if int(doc_ver.split(".")[1]) >= 18:
        assert '<figure class="align-center" id="needflow-index-0">' in index_html
    else:
        assert '<div class="figure align-center" id="needflow-index-0">' in index_html

    assert "No needs passed the filters" in index_html

    page_html = Path(app.outdir, "page.html").read_text()
    assert "SPEC_1 [[../index.html#SPEC_1]]" in page_html
    assert "SPEC_2 [[../index.html#SPEC_2]]" in page_html
    assert "STORY_1 [[../index.html#STORY_1]]" in page_html
    assert "STORY_1.1 [[../index.html#STORY_1.1]]" in page_html
    assert "STORY_1.2 [[../index.html#STORY_1.2]]" in page_html
    assert "STORY_1.subspec [[../index.html#STORY_1.subspec]]" in page_html
    assert "STORY_2 [[../index.html#STORY_2]]" in page_html
    assert "STORY_2.another_one [[../index.html#STORY_2.another_one]]" in page_html


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needflow_incl_child_needs"}], indirect=True
)
def test_doc_build_needflow_incl_child_needs(test_app):
    app = test_app
    app.build()

    html = Path(app.outdir, "index.html").read_text()
    assert html
    assert "@startuml" in html
    assert "[[../index.html#STORY_1]]" in html
    assert "[[../index.html#STORY_1.1]]" in html
    assert "[[../index.html#STORY_1.2]]" in html
    assert "[[../index.html#STORY_2]]" in html
    assert "[[../index.html#STORY_2.3]]" in html
    assert "[[../index.html#SPEC_1]]" in html
    assert "[[../index.html#SPEC_2]]" in html
    assert "[[../index.html#SPEC_3]]" in html
    assert "[[../index.html#SPEC_4]]" in html
    assert "[[../index.html#STORY_3]]" in html
    assert "[[../index.html#SPEC_5]]" in html
    assert "@enduml" in html
