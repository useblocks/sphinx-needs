from pathlib import Path

import pytest
from docutils import __version__ as doc_ver


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needflow"}],
    indirect=True,
)
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

    empty_needflow_with_debug = Path(
        app.outdir, "empty_needflow_with_debug.html"
    ).read_text()
    assert "No needs passed the filters" in empty_needflow_with_debug


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needflow_incl_child_needs"}],
    indirect=True,
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
    assert index_html.count("@startuml") == 1
    assert index_html.count("[[../index.html#STORY_1]]") == 2
    assert index_html.count("[[../index.html#STORY_1.1]]") == 2
    assert index_html.count("[[../index.html#STORY_1.2]]") == 2
    assert index_html.count("[[../index.html#STORY_2]]") == 2
    assert index_html.count("[[../index.html#STORY_2.3]]") == 2
    assert index_html.count("[[../index.html#SPEC_1]]") == 2
    assert index_html.count("[[../index.html#SPEC_2]]") == 2
    assert index_html.count("[[../index.html#SPEC_3]]") == 2
    assert index_html.count("[[../index.html#SPEC_4]]") == 2
    assert index_html.count("[[../index.html#STORY_3]]") == 2
    assert index_html.count("[[../index.html#SPEC_5]]") == 2
    assert index_html.count("@enduml") == 1

    single_parent_need_filer_html = Path(
        app.outdir, "single_parent_need_filer.html"
    ).read_text()
    assert single_parent_need_filer_html
    assert single_parent_need_filer_html.count("@startuml") == 1
    assert single_parent_need_filer_html.count("[[../index.html#STORY_3]]") == 2
    assert single_parent_need_filer_html.count("@enduml") == 1
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

    single_child_with_child_need_filter_html = Path(
        app.outdir, "single_child_with_child_need_filter.html"
    ).read_text()
    assert single_child_with_child_need_filter_html
    assert single_child_with_child_need_filter_html.count("@startuml") == 1
    assert (
        single_child_with_child_need_filter_html.count("[[../index.html#STORY_2]]") == 2
    )
    assert single_child_with_child_need_filter_html.count("@enduml") == 1
    assert "[[../index.html#STORY_1]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_1.1]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_1.2]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_2.3]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_1]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_2]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_3]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_4]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_3]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_5]]" not in single_child_with_child_need_filter_html

    single_child_need_filter_html = Path(
        app.outdir, "single_child_need_filter.html"
    ).read_text()
    assert single_child_need_filter_html
    assert single_child_need_filter_html.count("@startuml") == 1
    assert single_child_need_filter_html.count("[[../index.html#SPEC_1]]") == 2
    assert single_child_need_filter_html.count("@enduml") == 1
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

    grandy_and_child_html = Path(app.outdir, "grandy_and_child.html").read_text()
    assert grandy_and_child_html
    assert grandy_and_child_html.count("@startuml") == 1
    assert grandy_and_child_html.count("[[../index.html#STORY_1]]") == 2
    assert grandy_and_child_html.count("[[../index.html#SPEC_1]]") == 2
    assert grandy_and_child_html.count("[[../index.html#SPEC_2]]") == 2
    assert grandy_and_child_html.count("@enduml") == 1
    assert "[[../index.html#STORY_1.1]]" not in grandy_and_child_html
    assert "[[../index.html#STORY_1.2]]" not in grandy_and_child_html
    assert "[[../index.html#STORY_2]]" not in grandy_and_child_html
    assert "[[../index.html#STORY_2.3]]" not in grandy_and_child_html
    assert "[[../index.html#SPEC_3]]" not in grandy_and_child_html
    assert "[[../index.html#SPEC_4]]" not in grandy_and_child_html
    assert "[[../index.html#STORY_3]]" not in grandy_and_child_html
    assert "[[../index.html#SPEC_5]]" not in grandy_and_child_html
