import os
from pathlib import Path

import pytest
from docutils import __version__ as doc_ver
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needs_filter_data"}],
    indirect=True,
)
def test_doc_needs_filter_data_html(test_app):
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    print(warnings)
    assert warnings == [
        "srcdir/filter_code.rst:34: WARNING: malformed function signature: 'own_filter_code(' [needs.filter_func]",
        "srcdir/filter_code.rst:43: WARNING: malformed function signature: 'own_filter_code(' [needs.filter_func]",
        "srcdir/filter_code.rst:39: WARNING: malformed function signature: 'my_pie_filter_code(' [needs.filter_func]",
        "srcdir/filter_code.rst:48: WARNING: malformed function signature: 'my_pie_filter_code(' [needs.filter_func]",
        "WARNING: variant_not_equal_current_variant: failed",
        "\t\tfailed needs: 1 (extern_filter_story_002)",
        "\t\tused filter: variant != current_variant [needs.warnings]",
    ]

    index_html = Path(app.outdir, "index.html").read_text()
    filter_code = Path(app.outdir, "filter_code.html").read_text()

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
    assert (
        '<td class="needs_tags"><p>my_tag<em>; </em>current_variant</p></td>'
        in index_html
    )
    assert (
        '<span class="caption-text">Filter code func table with multiple dots filter function path</span>'
        in filter_code
    )

    # check needflow works
    if int(doc_ver.split(".")[1]) >= 18:
        assert '<figure class="align-center" id="needflow-index-0">' in index_html
    else:
        assert '<div class="figure align-center" id="needflow-index-0">' in index_html

    # check needextract works
    assert '<div class="docutils container" id="needextract-index-0">' in index_html
    assert "needs_style_green_border" in index_html

    # check needpie works
    assert '<img alt="_images/need_pie_dba00.svg" id="needpie-index-0"' in index_html
    assert (
        '<img alt="_images/need_pie_446e9.svg" id="needpie-filter_code-0"'
        in filter_code
    )
    assert (
        '<img alt="_images/need_pie_fac86.svg" id="needpie-filter_code-1"'
        in filter_code
    )
    # check needextend works
    assert (
        '<span class="needs_tags"><span class="needs_label">tags: </span>'
        '<span class="needs_data_container"><span class="needs_data">test_tag_001</span>'
        '<span class="needs_spacer">, </span><span class="needs_data">current_variant</span></span>'
        in index_html
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needs_filter_data"}],
    indirect=True,
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
