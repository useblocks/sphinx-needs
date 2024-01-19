from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/filter_doc"}], indirect=True)
def test_filter_build_html(test_app):
    app = test_app
    app.build()
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
        'href="#CHILD_1_STORY" title="STORY_PARENT">CHILD_1_STORY</a></span></span></div>' in html_5
    )
    assert (
        '<div class="line">parent needs: <span class="parent_needs"><span><a class="reference internal" '
        'href="#CHILD_1_STORY" title="CHILD_2_STORY">CHILD_1_STORY</a></span></span></div>' in html_5
    )

    html_6 = Path(app.outdir, "filter_no_needs.html").read_text()
    assert html_6.count("No needs passed the filters") == 1
    assert html_6.count("No required needs found in table") == 1
    assert html_6.count("No required needs found in list") == 0  # the list will not be shown, seems dead code
    assert "</tbody>\n<p></p>\n</table>" in html_6
