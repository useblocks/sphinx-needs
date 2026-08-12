"""Tests for the options that are accepted only for ubCode compatibility.

ubCode understands a handful of directive options that Sphinx-Needs has no
equivalent for. Sphinx-Needs accepts them, so that documents authored for ubCode
still build, but they must never influence the Sphinx build in any way.
"""

from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.directives.needflow._directive import (
    NeedflowGraphiz,
    NeedflowPlantuml,
)
from sphinx_needs.directives.needlist import Needlist
from sphinx_needs.directives.needsequence import Needsequence
from sphinx_needs.directives.needtable import Needtable

COMPAT_OPTIONS = ("cypher", "max_items", "width", "height")
"""All options that are accepted for ubCode compatibility and then ignored."""

VIEW_NODES = (Needlist, Needtable, NeedflowPlantuml, NeedflowGraphiz, Needsequence)
"""The node classes created by the directives that accept the compat options."""


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_ubcode_compat"}],
    indirect=True,
)
def test_ubcode_compat_options_are_accepted(test_app: SphinxTestApp):
    """The compat options build cleanly and the directives still render.

    Without them in ``option_spec``, docutils reports an ``unknown option``
    error and replaces the whole directive with a system message, so none of the
    target anchors below would be written.
    """
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""

    html = Path(app.outdir, "index.html").read_text()
    for target_id in (
        "needlist-index-0",
        "needtable-index-0",
        "needflow-index-0",
        "needsequence-index-0",
    ):
        assert f'id="{target_id}"' in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_ubcode_compat"}],
    indirect=True,
)
def test_ubcode_compat_options_are_ignored(test_app: SphinxTestApp):
    """The compat options are dropped, they never reach a node.

    This is what makes them true no-ops: the directives build their node
    attributes from closed literals, so an accepted option that is not collected
    cannot reach the doctree, ``needs.json``, or any output.
    """
    app = test_app
    app.build()

    doctree = app.env.get_doctree("index")
    view_nodes = [node for node in doctree.findall() if isinstance(node, VIEW_NODES)]
    assert {type(node).__name__ for node in view_nodes} == {
        "Needlist",
        "Needtable",
        "NeedflowPlantuml",
        "Needsequence",
    }

    leaked = {
        (type(node).__name__, option)
        for node in view_nodes
        for option in COMPAT_OPTIONS
        if option in node.attributes
    }
    assert leaked == set()
