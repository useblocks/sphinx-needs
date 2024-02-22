from pathlib import Path

import pytest
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/filter_doc"}],
    indirect=True,
)
def test_filter_build_html(test_app):
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir), "srcdir")
    ).splitlines()
    for w in warnings:
        print(w)
    assert warnings == [
        "srcdir/index.rst:51: WARNING: Filter 'xxx' not valid. Error: name 'xxx' is not defined. [needs.filter]",
        "srcdir/index.rst:54: WARNING: Filter 'yyy' not valid. Error: name 'yyy' is not defined. [needs.filter]",
        "srcdir/index.rst:57: WARNING: Filter 'zzz' not valid. Error: name 'zzz' is not defined. [needs.filter]",
    ]

    html = Path(app.outdir, "index.html").read_text()
    assert "story_a_1" in html
    assert "story_b_1" not in html
    assert "story_a_b_1" in html

    assert "req_a_1" not in html
    assert "req_b_1" not in html
    assert "req_c_1" in html

    html_2 = Path(app.outdir, "filter_tags_or.html").read_text()
    assert "req_a" in html_2
    assert "req_b" in html_2
    assert "req_c" in html_2

    html_3 = Path(app.outdir, "filter_all.html").read_text()
    assert "req_a_not" not in html_3
    assert "req_b_found" in html_3
    assert "req_c_not" not in html_3
    assert "req_d_found" in html_3
    assert "story_1_not" not in html_3
    assert "story_2_found" in html_3
    assert "my_test" in html_3

    html_4 = Path(app.outdir, "filter_search.html").read_text()
    assert "search_a" in html_4
    assert "search_b" not in html_4
    assert "search_c" not in html_4
    assert "search_d" not in html_4
    assert "search_2_1" in html_4
    assert "search_2_2" in html_4
    assert "test_email" in html_4

    # nested needs
    html_5 = Path(app.outdir, "nested_needs.html").read_text()
    assert "STORY_PARENT" in html_5
    assert "CHILD_1_STORY" in html_5
    assert "CHILD_2_STORY" in html_5
    assert (
        '<div class="line">child needs: <span class="parent_needs"><span><a class="reference internal" '
        'href="#CHILD_1_STORY" title="STORY_PARENT">CHILD_1_STORY</a></span></span></div>'
        in html_5
    )
    assert (
        '<div class="line">parent needs: <span class="parent_needs"><span><a class="reference internal" '
        'href="#CHILD_1_STORY" title="CHILD_2_STORY">CHILD_1_STORY</a></span></span></div>'
        in html_5
    )

    html_6 = Path(app.outdir, "filter_no_needs.html").read_text()
    assert html_6.count("No needs passed the filters") == 6
    assert html_6.count("Should show no specific message and no default message") == 6
    assert html_6.count("<figure class=") == 3

    assert html_6.count("got filter warning from needtable") == 1
    assert "no filter warning from needtable" not in html_6
    assert html_6.count('<table class="NEEDS_DATATABLES') == 1

    assert html_6.count("got filter warning from needlist") == 1
    assert "no filter warning from needlist" not in html_6

    assert html_6.count("got filter warning from needflow") == 1
    assert "no filter warning from needflow" not in html_6

    assert html_6.count("got filter warning from needgant") == 1
    assert "no filter warning from needgant" not in html_6

    assert (
        html_6.count("got filter warning from needsequence") == 1
    )  # maybe fixed later, now always start node is shown
    assert "no filter warning from needsequence" not in html_6

    assert html_6.count("got filter warning from needpie") == 1
    assert "no filter warning from needpie" not in html_6
    assert '<img alt="_images/need_pie_' in html_6

    assert html_6.count('<p class="needs_filter_warning"') == 18
