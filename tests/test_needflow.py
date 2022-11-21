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

    # stdout warnings
    warning = app._warning
    warnings = warning.getvalue()
    # plantuml shall not return any warnings:
    assert "WARNING: error while running plantuml" not in warnings

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

    empty_needflow_with_debug = Path(app.outdir, "empty_needflow_with_debug.html").read_text()
    assert "No needs passed the filters" in empty_needflow_with_debug


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needflow_incl_child_needs"}], indirect=True
)
def test_doc_build_needflow_incl_child_needs(test_app):
    app = test_app
    app.build()

    # stdout warnings
    warning = app._warning
    warnings = warning.getvalue()
    # plantuml shall not return any warnings:
    assert "WARNING: error while running plantuml" not in warnings

    index_html = Path(app.outdir, "index.html").read_text()
    assert index_html
    assert "@startuml" in index_html
    assert "[[../index.html#STORY_1]]" in index_html
    assert "[[../index.html#STORY_1.1]]" in index_html
    assert "[[../index.html#STORY_1.2]]" in index_html
    assert "[[../index.html#STORY_2]]" in index_html
    assert "[[../index.html#STORY_2.3]]" in index_html
    assert "[[../index.html#SPEC_1]]" in index_html
    assert "[[../index.html#SPEC_2]]" in index_html
    assert "[[../index.html#SPEC_3]]" in index_html
    assert "[[../index.html#SPEC_4]]" in index_html
    assert "[[../index.html#STORY_3]]" in index_html
    assert "[[../index.html#SPEC_5]]" in index_html
    assert "@enduml" in index_html

    single_parent_need_filer_html = Path(app.outdir, "single_parent_need_filer.html").read_text()
    assert "@startuml" in single_parent_need_filer_html
    assert "[[../index.html#STORY_3]]"  in single_parent_need_filer_html
    assert "@enduml" in single_parent_need_filer_html
    assert "[[../index.html#STORY_1]]" not in single_parent_need_filer_html
    assert "[[../index.html#STORY_1.1]]" not in single_parent_need_filer_html
    assert "[[../index.html#STORY_1.2]]" not in single_parent_need_filer_html
    assert "[[../index.html#STORY_2]]" not in single_parent_need_filer_html
    assert "[[../index.html#STORY_2.3]]" not in single_parent_need_filer_html
    assert "[[../index.html#SPEC_1]]" not in single_parent_need_filer_html
    assert "[[../index.html#SPEC_2]]" not in single_parent_need_filer_html
    assert "[[../index.html#SPEC_3]]" not in single_parent_need_filer_html
    assert "[[../index.html#SPEC_4]]" not in single_parent_need_filer_html
    assert "[[../index.html#SPEC_5]]" not in single_parent_need_filer_html
    

    single_child_with_child_need_filter_html = Path(app.outdir, "single_child_with_child_need_filter.html").read_text()
    assert "@startuml" in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_2]]" in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_2.3]]" in single_child_with_child_need_filter_html
    assert "@enduml" in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_1]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_1.1]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_1.2]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_1]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_2]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_3]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_4]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_3]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_5]]" not in single_child_with_child_need_filter_html

    single_child_need_filter_html = Path(app.outdir, "single_child_need_filter.html").read_text()
    assert "@startuml" in single_child_need_filter_html
    assert "[[../index.html#SPEC_1]]" in single_child_need_filter_html
    assert "@enduml" in single_child_need_filter_html
    assert "[[../index.html#STORY_1]]" not in single_child_need_filter_html
    assert "[[../index.html#STORY_1.1]]" not in single_child_need_filter_html
    assert "[[../index.html#STORY_1.2]]" not in single_child_need_filter_html
    assert "[[../index.html#STORY_2]]" not in single_child_need_filter_html
    assert "[[../index.html#STORY_2.3]]" not in single_child_need_filter_html
    assert "[[../index.html#SPEC_2]]" not in single_child_need_filter_html
    assert "[[../index.html#SPEC_3]]" not in single_child_need_filter_html
    assert "[[../index.html#SPEC_4]]" not in single_child_need_filter_html
    assert "[[../index.html#STORY_3]]" not in single_child_need_filter_html
    assert "[[../index.html#SPEC_5]]" not in single_child_need_filter_html
