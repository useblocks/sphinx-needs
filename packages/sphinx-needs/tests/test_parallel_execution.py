import re
from pathlib import Path

import pytest
from sphinx.util.parallel import parallel_available

from sphinx_needs_testkit import build_warnings


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/parallel_doc",
            "parallel": 4,
        }
    ],
    indirect=True,
)
@pytest.mark.skipif(not parallel_available, reason="Parallel execution not supported")
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert warnings[0] == (
        "WARNING: needs_filter_data is deprecated and will be removed in a future version. "
        "Use needs_variant_data instead. [needs.deprecated]"
    )
    # page_1 and page_5 both declare STORY_PAGE_1. Which one is reported, and how, depends on
    # how the workers were scheduled: read in the same process the second one fails to be
    # created (page_5, documents are read in order); read in different processes the one
    # whose results are merged second is the duplicate, and that can be either page.
    duplicate = re.compile(
        r"<srcdir>/page_[15]\.rst:4: WARNING: A need with ID STORY_PAGE_1 already exists, "
        r"title: '(duplicate|page_1 Story)'\. \[needs\.duplicate_id\]"
    )
    assert len(warnings) == 2, warnings
    assert duplicate.fullmatch(warnings[1]) or warnings[1] == (
        "<srcdir>/page_5.rst:4: WARNING: Need could not be created: "
        "A need with ID 'STORY_PAGE_1' already exists. [needs.create_need]"
    ), warnings[1]

    index_html = Path(app.outdir, "index.html").read_text()
    assert "<h1>PARALLEL TEST DOCUMENT" in index_html
    assert "SP_TOO_001" in index_html

    page3_html = Path(app.outdir, "page_3.html").read_text()
    assert "Page 3" in page3_html
    assert "Test for Variants" in page3_html
    assert "SP_0013" in page3_html
    assert (
        '<span class="needs_author"><span class="needs_label">author: </span>'
        '<span class="needs_data">Daniel Woste</span></span>' in page3_html
    )
    assert (
        """<thead>
<tr class="row-odd"><th class="head"><p>ID</p></th>
<th class="head"><p>Title</p></th>
<th class="head"><p>Status</p></th>
<th class="head"><p>Type</p></th>
<th class="head"><p>Outgoing</p></th>
<th class="head"><p>Tags</p></th>
</tr>
</thead>
"""
        in page3_html
    )
    assert "SP_001" in page3_html
    assert "SP_TOO_001" in page3_html
    assert "SP_001.107" in page3_html
    assert "SPEC_PAGE_1" in page3_html
    assert "STORY_PAGE_2" in page3_html
    assert "SP_001" in page3_html

    page1_html = Path(app.outdir, "page_1.html").read_text()
    assert "Page 1" in page1_html
    assert "SPEC_PAGE_1" in page1_html
    # The same scheduling decides which story holds STORY_PAGE_1 in the output: the one
    # the warning above does NOT name. SPEC_PAGE_1 links to the id either way, so only
    # the target page of that link, and which title renders, follow the winner.
    if "page_1.rst" in warnings[1]:
        assert "page_1 Story" not in page1_html
        page5_html = Path(app.outdir, "page_5.html").read_text()
        assert "duplicate" in page5_html
        link_target = "page_5.html#STORY_PAGE_1"
    else:
        assert "page_1 Story" in page1_html
        link_target = "#STORY_PAGE_1"
    assert (
        '<div class="line">links outgoing: <span '
        f'class="links"><span><a class="reference internal" href="{link_target}" '
        'title="SPEC_PAGE_1">STORY_PAGE_1</a></span></span></div>' in page1_html
    )
    page2_html = Path(app.outdir, "page_2.html").read_text()
    assert "Page 2" in page2_html
    assert "page_2 Spec" in page2_html
    assert "STORY_PAGE_2" in page2_html
    assert (
        '<div class="line">links incoming: <span '
        'class="links"><span><a class="reference internal" href="#SPEC_PAGE_2" '
        'title="STORY_PAGE_2">SPEC_PAGE_2</a></span></span></div>' in page2_html
    )
    page4_html = Path(app.outdir, "page_4.html").read_text()
    assert "Page 4" in page4_html
    assert "Test needextract" in page4_html
    assert "SP_001" in page4_html
    assert 'href="#SP_001.107"' in page4_html
    assert "needs_style_blue_border" in page4_html
