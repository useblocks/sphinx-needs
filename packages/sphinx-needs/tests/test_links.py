import os
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_links", "no_plantuml": False}],
    indirect=True,
)
def test_links_html(test_app):
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    # print(warnings)
    assert warnings == [
        'WARNING: Config option "needs_extra_links" is deprecated. Please use "needs_links" instead. [needs.deprecated]',
        "srcdir/index.rst:7: WARNING: Need 'REQ_001' has unknown outgoing link 'DEAD_LINK_NOT_ALLOWED' in field 'links' [needs.link_outgoing]",
        "srcdir/index.rst:7: WARNING: Need 'REQ_001' has unknown outgoing link 'DEAD_LINK_ALLOWED' in field 'links' [needs.link_outgoing]",
        "srcdir/index.rst:7: WARNING: Need 'REQ_001' has unknown outgoing link 'DEAD_LINK_ALLOWED' in field 'blocks' [needs.link_outgoing]",
        "srcdir/index.rst:12: WARNING: Need 'REQ_002' has unknown outgoing link 'ARGH_123' in field 'links' [needs.link_outgoing]",
        "srcdir/index.rst:49: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'tests' [needs.link_outgoing]",
    ]

    html = Path(app.outdir, "index.html").read_text()
    assert "TEST_001" in html
    assert "tested by" in html
    assert "tests" in html
    assert "blocked by" in html
    assert "blocks" in html

    # Check for correct dead_links handling
    assert '<span class="needs_dead_link">DEAD_LINK_ALLOWED</span>' in html
    assert (
        '<span class="needs_dead_link forbidden">DEAD_LINK_NOT_ALLOWED</span>' in html
    )
    assert '<span class="needs_dead_link forbidden">REQ_005.invalid</span>' in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "latex", "srcdir": "doc_test/doc_links", "no_plantuml": False}],
    indirect=True,
)
def test_links_latex(test_app):
    app = test_app
    app.build()
    tex = Path(app.outdir, "needstestdocs.tex").read_text()
    assert "TEST_001" in tex
    assert "tested by" in tex
    assert "tests" in tex
    assert "blocked by" in tex
    assert "blocks" in tex
