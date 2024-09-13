import os
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_needs.api.need import NeedsStatusNotAllowed, NeedsTagNotAllowed


def get_warnings(app: SphinxTestApp):
    return (
        strip_colors(app._warning.getvalue())
        .replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
        .splitlines()
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/broken_doc", "no_plantuml": True}],
    indirect=True,
)
def test_duplicate_id(test_app: SphinxTestApp):
    test_app.build()
    assert get_warnings(test_app) == [
        "<srcdir>/index.rst:11: WARNING: A need with ID SP_TOO_001 already exists, title: 'Command line interface'. [needs.duplicate_id]"
    ]
    html = (test_app.outdir / "index.html").read_text()
    assert "<h1>BROKEN DOCUMENT" in html
    assert "SP_TOO_001" in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/broken_links", "no_plantuml": True}],
    indirect=True,
)
def test_broken_links(test_app: SphinxTestApp):
    app = test_app
    app.build()

    assert get_warnings(test_app) == [
        "<srcdir>/index.rst:12: WARNING: Need 'SP_TOO_002' has unknown outgoing link 'NOT_WORKING_LINK' in field 'links' [needs.link_outgoing]",
        "<srcdir>/index.rst:21: WARNING: linked need BROKEN_LINK not found [needs.link_ref]",
    ]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/broken_statuses"}],
    indirect=True,
)
def test_broken_statuses(test_app: SphinxTestApp):
    with pytest.raises(NeedsStatusNotAllowed):
        test_app.build()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/broken_syntax_doc",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_broken_syntax(test_app: SphinxTestApp):
    test_app.build()

    assert [li for li in get_warnings(test_app) if li.startswith("<srcdir>")] == [
        '<srcdir>/index.rst:4: ERROR: Error in "spec" directive:',
        '<srcdir>/index.rst:11: ERROR: Error in "spec" directive:',
        '<srcdir>/index.rst:19: ERROR: Error in "spec" directive:',
    ]

    html = Path(test_app.outdir, "index.html").read_text()
    assert "SP_TOO_001" not in html
    assert "SP_TOO_002" not in html
    assert "SP_TOO_003" not in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/broken_tags"}],
    indirect=True,
)
def test_broken_tags(test_app: SphinxTestApp):
    with pytest.raises(NeedsTagNotAllowed):
        test_app.build()
