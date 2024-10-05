from pathlib import Path

import pytest

from sphinx_needs.api import get_needs_view


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_list2need"}],
    indirect=True,
)
def test_doc_list2need_html(test_app, snapshot):
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""

    view = get_needs_view(app)
    assert dict(view) == snapshot

    index_html = Path(app.outdir, "index.html").read_text()
    assert "NEED-002" in index_html
    assert "Sub-Need on level 3" in index_html
    assert (
        '<a class="reference internal" href="#test"><span class="std std-ref">Test chapter</span></a>'
        in index_html
    )

    # Check parent-child linking (nested)
    assert (
        '<span class="parent_needs"><span><a class="reference internal" href="#NEED-002" title="NEED-003">NEED-002</a></span></span>'
        in index_html
    )

    options_html = Path(app.outdir, "options.html").read_text()

    assert '<span class="needs_label">status: </span>' in options_html
    assert '<span class="needs_data">done</span>' in options_html
    assert '<span class="needs_data">in progress</span>' in options_html

    # check for 2 links
    assert (
        '<div class="line">links outgoing: <span class="links"><span><a class="reference internal" href="#NEED-1" '
        'title="NEED-3">NEED-1</a>, <a class="reference internal" href="#NEED-2" title="NEED-3">NEED-2</a></span>'
        "</span></div>" in options_html
    )

    # check for option defined in own, new line
    assert (
        '<div class="line">links outgoing: <span class="links"><span><a class="reference internal" href="#NEED-3" '
        'title="NEED-4">NEED-3</a></span></span></div>' in options_html
    )

    links_down_html = Path(app.outdir, "links_down.html").read_text()

    assert (
        '<div class="line">checks: <span class="checks"><span><a class="reference internal" href="#NEED-B" '
        'title="NEED-A">NEED-B</a></span></span></div>' in links_down_html
    )

    assert (
        '<div class="line">triggers: <span class="triggers"><span><a class="reference internal" href="#NEED-C" '
        'title="NEED-B">NEED-C</a></span></span></div>' in links_down_html
    )

    assert (
        '<div class="line">is triggered by: <span class="triggers"><span><a class="reference internal" '
        'href="#NEED-B" title="NEED-C">NEED-B</a></span></span></div>'
        in links_down_html
    )
