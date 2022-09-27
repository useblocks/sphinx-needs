from pathlib import Path

import pytest
from docutils import __version__ as doc_ver


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needs_filter_data"}], indirect=True
)
def test_doc_needs_filter_data_html(test_app):
    app = test_app
    app.build()
    index_html = Path(app.outdir, "index.html").read_text()

    import sphinx

    if sphinx.__version__.startswith("3.5"):
        return

    # Check need_count works
    assert "The amount of needs that belong to current variants: 6" in index_html

    # Check needlist works
    assert (
        '<div class="line"><a class="reference external" href="#extern_filter_test_003">'
        "extern_filter_test_003: Test Example 3</a></div>" in index_html
    )

    # Check needtable works
    assert '<span class="caption-text">Example table' in index_html
    assert '<td class="needs_title"><p>Test Example 3</p></td>' in index_html
    assert '<td class="needs_tags"><p>my_tag<em>; </em>current_variant</p></td>' in index_html

    # check needflow works
    if int(doc_ver.split(".")[1]) >= 18:
        assert '<figure class="align-center" id="needflow-index-0">' in index_html
    else:
        assert '<div class="figure align-center" id="needflow-index-0">' in index_html

    # check needextract works
    assert '<div class="docutils container" id="needextract-index-0">' in index_html
    assert "needs_style_green_border" in index_html

    # check needpie works
    assert '<img alt="_images/need_pie_dba00.png" id="needpie-index-0"' in index_html

    # check needextend works
    assert (
        '<span class="needs_tags"><span class="needs_label">tags: </span>'
        '<span class="needs_data_container"><span class="needs_data">test_tag_001</span>'
        '<span class="needs_spacer">, </span><span class="needs_data">current_variant</span></span>' in index_html
    )

    # check needs_warnings works
    warning = app._warning
    warnings = warning.getvalue()

    # check warnings contents
    assert "WARNING: variant_not_equal_current_variant: failed" in warnings
    assert "failed needs: 1 (extern_filter_story_002)" in warnings
    assert "used filter: variant != current_variant" in warnings


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needs_filter_data"}], indirect=True
)
def test_doc_needs_filter_code(test_app):
    app = test_app
    app.build()
    code_html = Path(app.outdir, "filter_code.html").read_text()

    assert '<span class="caption-text">Filter code table</span>' in code_html
    assert '<span class="caption-text">Filter code func table</span>' in code_html

    # code content data
    assert "extern_filter_story_001" in code_html
    assert "extern_filter_story_002" in code_html

    # code func data
    assert "extern_filter_test_003" in code_html

    # check needpie filter func code data
    assert '<img alt="_images/need_pie_' in code_html

    code_args_html = Path(app.outdir, "filter_code_args.html").read_text()
    assert '<a class="reference internal" href="#impl1">impl1</a>' in code_args_html
