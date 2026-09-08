from __future__ import annotations

import json
import os.path
import sys
from pathlib import Path

import docutils
import pytest
from lxml import html as html_parser
from sphinx import version_info
from sphinx.testing.util import SphinxTestApp
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needtable import Needtable


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_basic"}],
    indirect=True,
)
def test_build_html(test_app: SphinxTestApp, snapshot_doctree):
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""

    doctree = app.env.get_doctree("index")

    # Normalize the tree for old docutils versions.
    if docutils.__version_info__ < (0, 22):
        for node in doctree.traverse():
            if isinstance(node, Needtable):
                if node.get("show_filters") is False:
                    node["show_filters"] = 0
                if node.get("show_parts") is False:
                    node["show_parts"] = 0

    # Check if doctree is correct.
    assert doctree == snapshot_doctree

    # Basic checks for the generated html.
    html = Path(app.outdir, "index.html").read_text()
    assert "<h1>TEST DOCUMENT" in html
    assert "ST_001" in html

    # Check if static files got copied correctly.
    build_dir = Path(app.outdir) / "_static" / "sphinx-needs" / "libs" / "html"
    files = [f for f in build_dir.glob("**/*") if f.is_file()]
    assert build_dir / "sphinx_needs_collapse.js" in files
    assert build_dir / "needstable.js" in files
    assert build_dir / "needstable.css" in files
    # the whole vendored DataTables tree went with the enhancer that replaced it
    assert not [f for f in files if "datatables" in f.name.lower()]


@pytest.mark.skipif(
    sys.platform == "win32", reason="assert fails on windows, need to fix later."
)
@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_basic"}],
    indirect=True,
)
def test_html_head_files(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""

    # check usage in project root level
    html_path = str(Path(app.outdir, "index.html"))
    root_tree = html_parser.parse(html_path)
    script_nodes = root_tree.xpath("/html/head/script")
    script_files = [x.attrib["src"].rsplit("?", 1)[0] for x in script_nodes]
    assert script_files.count("_static/sphinx-needs/libs/html/needstable.js") == 1

    # the tag has to be DEFERRED, and `loading_method` is not an HTML attribute: only
    # `Sphinx.add_js_file` translates that keyword, and the per-page registration has to
    # go through the builder, which writes every keyword into the tag verbatim
    script = next(
        node
        for node in script_nodes
        if "libs/html/needstable.js" in node.attrib.get("src", "")
    )
    assert script.attrib.get("defer") is not None, dict(script.attrib)
    assert "loading_method" not in script.attrib, dict(script.attrib)

    link_nodes = root_tree.xpath("/html/head/link")
    link_files = [x.attrib["href"].rsplit("?", 1)[0] for x in link_nodes]
    assert link_files.count("_static/sphinx-needs/libs/html/needstable.css") == 1
    assert link_files.count("_static/sphinx-needs/modern.css") == 1

    # Checks if not \ (Backslash) is found as path of js/css files
    # This can happen when working on Windows (would be a bug ;) )
    for head_file in script_files + link_files:
        assert "\\" not in head_file

    # the table assets go on the pages that have a table, and nowhere else (#462).
    # `search.html` and `genindex.html` have no doctree at all, and used to carry the
    # whole 2.26 MB DataTables bundle
    for pagename in ("search.html", "genindex.html"):
        tree = html_parser.parse(str(Path(app.outdir, pagename)))
        assets = [
            node.attrib["src" if node.tag == "script" else "href"].rsplit("?", 1)[0]
            for node in tree.xpath("/html/head/script") + tree.xpath("/html/head/link")
        ]
        assert "_static/sphinx-needs/libs/html/needstable.js" not in assets, pagename
        assert "_static/sphinx-needs/libs/html/needstable.css" not in assets, pagename


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "singlehtml",
            "srcdir": "doc_test/doc_basic",
        }
    ],
    indirect=True,
)
def test_build_singlehtml(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "latex", "srcdir": "doc_test/doc_basic"}],
    indirect=True,
)
def test_build_latex(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""

    print([p.name for p in Path(app.outdir).iterdir()])

    latex_file = Path(app.outdir, "needs.tex")
    assert latex_file
    latex_content = latex_file.read_text()

    # Check table generated by Sphinxneeds has correct caption
    assert (
        "\\sphinxcaption{Table from sphinx\\sphinxhyphen{}needs \\textquotesingle"
        "{}needtable\\textquotesingle{} directive}" in latex_content
    )

    # Check that the ST_001 label is only created once in the LaTeX output.  Split
    # on the string, which should split latex_content into two.
    assert len(latex_content.split(r"\label{\detokenize{index:ST_001}}")) == 2


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "epub", "srcdir": "doc_test/doc_basic"}],
    indirect=True,
)
def test_build_epub(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "json", "srcdir": "doc_test/doc_basic"}],
    indirect=True,
)
def test_build_json(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_basic"}],
    indirect=True,
)
def test_build_needs(test_app: SphinxTestApp, snapshot):
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""

    schema = SphinxNeedsData(app.env).get_schema()
    assert {s.name: s for s in schema.iter_all_fields()} == snapshot(name="schema")

    json_text = Path(app.outdir, "needs.json").read_text()
    needs_data = json.loads(json_text)

    assert needs_data == snapshot(
        name="needs", exclude=props("created", "project", "creator")
    )


def test_sphinx_api_build(tmp_path: Path, make_app: type[SphinxTestApp]):
    """
    Tests a build via the Sphinx Build API.
    It looks like that there are scenarios where this specific build makes trouble but no others.
    """
    src_dir = os.path.join(os.path.dirname(__file__), "doc_test", "doc_basic")

    if version_info >= (7, 2):
        src_dir = Path(src_dir)
    else:
        from sphinx.testing.path import path

        src_dir = path(src_dir)
        tmp_path = path(str(tmp_path))

    sphinx_app = make_app(
        srcdir=src_dir,
        builddir=tmp_path,
        buildername="html",
        parallel=4,
        freshenv=True,
    )
    sphinx_app.build()
    assert sphinx_app.statuscode == 0
