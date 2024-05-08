import json
from pathlib import Path

import pytest
from sphinx.application import Sphinx
from sphinx.util.console import strip_colors
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needextend"}],
    indirect=True,
)
def test_doc_needextend_html(test_app: Sphinx, snapshot):
    app = test_app
    app.build()

    needs_data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs_data == snapshot(exclude=props("created"))

    index_html = Path(app.outdir, "index.html").read_text()
    assert "extend_test_003" in index_html

    assert (
        '<div class="line">links outgoing: <span class="links"><span><a class="reference internal" href="#extend_'
        'test_004" title="extend_test_003">extend_test_004</a></span></span></div>'
        in index_html
    )

    assert (
        '<div class="line">links outgoing: <span class="links"><span><a class="reference internal" href="#extend_'
        'test_003" title="extend_test_006">extend_test_003</a>, <a class="reference internal" href="#extend_'
        'test_004" title="extend_test_006">extend_test_004</a></span></span></div>'
        in index_html
    )

    page_1__html = Path(app.outdir, "page_1.html").read_text()
    assert (
        '<span class="needs_data_container"><span class="needs_data">tag_1</span><span class="needs_spacer">, '
        '</span><span class="needs_data">new_tag</span><span class="needs_spacer">, '
        '</span><span class="needs_data">another_tag</span></span>' in page_1__html
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needextend_unknown_id",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_needextend_unknown_id(test_app: Sphinx):
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).splitlines()
    assert warnings == [
        f"{Path(str(app.srcdir)) / 'index.rst'}:19: WARNING: Provided id 'unknown_id' for needextend does not exist. [needs.extend]"
    ]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needextend_dynamic"}],
    indirect=True,
)
def test_doc_needextend_dynamic(test_app, snapshot):
    app = test_app
    app.build()

    # for some reason this intermittently creates incorrect warnings about overriding visitors
    # assert app._warning.getvalue() == ""

    needs_data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs_data == snapshot(exclude=props("created"))
