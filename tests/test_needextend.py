import json
import os
from pathlib import Path

import pytest
from sphinx.application import Sphinx
from sphinx.util.console import strip_colors
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needextend", "no_plantuml": True}],
    indirect=True,
)
def test_doc_needextend_html(test_app: Sphinx, snapshot):
    app = test_app
    app.build()

    assert not app._warning.getvalue()

    needs_data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs_data == snapshot(exclude=props("created", "project", "creator"))

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
def test_doc_needextend_warnings(test_app: Sphinx):
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
    ).splitlines()
    # print(warnings)
    assert warnings == [
        "<srcdir>/index.rst:25: WARNING: Empty ID/filter argument in needextend directive. [needs.needextend]",
        "<srcdir>/index.rst:26: WARNING: Empty ID/filter argument in needextend directive. [needs.needextend]",
        "<srcdir>/index.rst:19: WARNING: Provided id 'unknown_id' for needextend does not exist. [needs.needextend]",
        "<srcdir>/index.rst:22: WARNING: Provided id 'id with space' for needextend does not exist. [needs.needextend]",
        "<srcdir>/index.rst:23: WARNING: Filter 'bad_filter' not valid. Error: name 'bad_filter' is not defined. [needs.filter]",
        "<srcdir>/index.rst:24: WARNING: Filter 'bad == filter' not valid. Error: name 'bad' is not defined. [needs.filter]",
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
    assert needs_data == snapshot(exclude=props("created", "project", "creator"))
