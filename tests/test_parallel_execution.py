import os
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from sphinx.util.parallel import parallel_available


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/parallel_doc",
            "parallel": 4,
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
@pytest.mark.skipif(not parallel_available, reason="Parallel execution not supported")
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    warnings = (
        strip_colors(app._warning.getvalue())
        .replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
        .strip()
    )
    assert (
        warnings
        == "<srcdir>/page_5.rst:4: WARNING: A need with ID STORY_PAGE_1 already exists, title: 'duplicate'. [needs.duplicate_id]"
    )

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
    assert "page_1 Story" in page1_html
    assert "SPEC_PAGE_1" in page1_html
    assert (
        '<div class="line">links outgoing: <span '
        'class="links"><span><a class="reference internal" href="#STORY_PAGE_1" '
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
