import os
from pathlib import Path, PurePosixPath

import pytest
from lxml import html as html_parser
from sphinx.config import Config
from sphinx.util.console import strip_colors


def _get_svg(config: Config, outdir: Path, file: str, id: str) -> str:
    root_tree = html_parser.parse(outdir / file)
    if config.needs_flow_engine == "plantuml":
        graph_nodes = root_tree.xpath(f"//figure[@id='{id}']/p/object")
        assert len(graph_nodes) == 1
        return (outdir / PurePosixPath(graph_nodes[0].attrib["data"])).read_text("utf8")
    else:
        graph_nodes = root_tree.xpath(f"//figure[@id='{id}']/div/a")
        assert len(graph_nodes) == 1
        return (outdir / PurePosixPath(graph_nodes[0].attrib["href"])).read_text("utf8")


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needflow",
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needflow",
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()

    # stdout warnings
    warnings = (
        strip_colors(app._warning.getvalue())
        .replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
        .strip()
    )
    assert warnings == ""

    outdir = Path(app.outdir)

    svg = _get_svg(app.config, outdir, "index.html", "needflow-index-0")
    for link in (
        "./index.html#SPEC_1",
        "./index.html#SPEC_2",
        "./index.html#STORY_1",
        # "./index.html#STORY_1.1",
        # "./index.html#STORY_1.2",
        # "./index.html#STORY_1.subspec",
        "./index.html#STORY_2",
        # "./index.html#STORY_2.another_one",
    ):
        assert link in svg
    assert "No needs passed the filters" in Path(app.outdir, "index.html").read_text()

    svg = _get_svg(app.config, outdir, "page.html", "needflow-page-0")
    for link in (
        "./index.html#SPEC_1",
        "./index.html#SPEC_2",
        "./index.html#STORY_1",
        # "./index.html#STORY_1.1",
        # "./index.html#STORY_1.2",
        # "./index.html#STORY_1.subspec",
        "./index.html#STORY_2",
        # "./index.html#STORY_2.another_one",
    ):
        assert link in svg

    svg = _get_svg(
        app.config,
        outdir,
        "needflow_with_root_id.html",
        "needflow-needflow_with_root_id-0",
    )
    print(svg)
    for link in ("SPEC_1", "STORY_1", "STORY_2"):
        assert link in svg

    assert "SPEC_2" not in svg

    empty_needflow_with_debug = Path(
        app.outdir, "empty_needflow_with_debug.html"
    ).read_text()
    assert "No needs passed the filters" in empty_needflow_with_debug


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needflow_incl_child_needs"}],
    indirect=True,
)
def test_doc_build_needflow_incl_child_needs(test_app):
    app = test_app
    app.build()

    # stdout warnings
    warning = app._warning
    warnings = warning.getvalue()
    # plantuml shall not return any warnings:
    assert "WARNING: error while running plantuml" not in warnings

    index_html = Path(app.outdir, "index.html").read_text()
    assert index_html
    assert index_html.count("@startuml") == 1
    assert index_html.count("[[../index.html#STORY_1]]") == 2
    assert index_html.count("[[../index.html#STORY_1.1]]") == 2
    assert index_html.count("[[../index.html#STORY_1.2]]") == 2
    assert index_html.count("[[../index.html#STORY_2]]") == 2
    assert index_html.count("[[../index.html#STORY_2.3]]") == 2
    assert index_html.count("[[../index.html#SPEC_1]]") == 2
    assert index_html.count("[[../index.html#SPEC_2]]") == 2
    assert index_html.count("[[../index.html#SPEC_3]]") == 2
    assert index_html.count("[[../index.html#SPEC_4]]") == 2
    assert index_html.count("[[../index.html#STORY_3]]") == 2
    assert index_html.count("[[../index.html#SPEC_5]]") == 2
    assert index_html.count("@enduml") == 1

    single_parent_need_filer_html = Path(
        app.outdir, "single_parent_need_filer.html"
    ).read_text()
    assert single_parent_need_filer_html
    assert single_parent_need_filer_html.count("@startuml") == 1
    assert single_parent_need_filer_html.count("[[../index.html#STORY_3]]") == 2
    assert single_parent_need_filer_html.count("@enduml") == 1
    assert "[[../index.html#STORY_1]]" not in single_parent_need_filer_html
    assert "[[../index.html#STORY_1.1]]" not in single_parent_need_filer_html
    assert "[[../index.html#STORY_1.2]]" not in single_parent_need_filer_html
    assert "[[../index.html#STORY_2]]" not in single_parent_need_filer_html
    assert "[[../index.html#STORY_2.3]]" not in single_parent_need_filer_html
    assert "[[../index.html#SPEC_1]]" not in single_parent_need_filer_html
    assert "[[../index.html#SPEC_2]]" not in single_parent_need_filer_html
    assert "[[../index.html#SPEC_3]]" not in single_parent_need_filer_html
    assert "[[../index.html#SPEC_4]]" not in single_parent_need_filer_html
    assert "[[../index.html#SPEC_5]]" not in single_parent_need_filer_html

    single_child_with_child_need_filter_html = Path(
        app.outdir, "single_child_with_child_need_filter.html"
    ).read_text()
    assert single_child_with_child_need_filter_html
    assert single_child_with_child_need_filter_html.count("@startuml") == 1
    assert (
        single_child_with_child_need_filter_html.count("[[../index.html#STORY_2]]") == 2
    )
    assert single_child_with_child_need_filter_html.count("@enduml") == 1
    assert "[[../index.html#STORY_1]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_1.1]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_1.2]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_2.3]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_1]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_2]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_3]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_4]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#STORY_3]]" not in single_child_with_child_need_filter_html
    assert "[[../index.html#SPEC_5]]" not in single_child_with_child_need_filter_html

    single_child_need_filter_html = Path(
        app.outdir, "single_child_need_filter.html"
    ).read_text()
    assert single_child_need_filter_html
    assert single_child_need_filter_html.count("@startuml") == 1
    assert single_child_need_filter_html.count("[[../index.html#SPEC_1]]") == 2
    assert single_child_need_filter_html.count("@enduml") == 1
    assert "[[../index.html#STORY_1]]" not in single_child_need_filter_html
    assert "[[../index.html#STORY_1.1]]" not in single_child_need_filter_html
    assert "[[../index.html#STORY_1.2]]" not in single_child_need_filter_html
    assert "[[../index.html#STORY_2]]" not in single_child_need_filter_html
    assert "[[../index.html#STORY_2.3]]" not in single_child_need_filter_html
    assert "[[../index.html#SPEC_2]]" not in single_child_need_filter_html
    assert "[[../index.html#SPEC_3]]" not in single_child_need_filter_html
    assert "[[../index.html#SPEC_4]]" not in single_child_need_filter_html
    assert "[[../index.html#STORY_3]]" not in single_child_need_filter_html
    assert "[[../index.html#SPEC_5]]" not in single_child_need_filter_html

    grandy_and_child_html = Path(app.outdir, "grandy_and_child.html").read_text()
    assert grandy_and_child_html
    assert grandy_and_child_html.count("@startuml") == 1
    assert grandy_and_child_html.count("[[../index.html#STORY_1]]") == 2
    assert grandy_and_child_html.count("[[../index.html#SPEC_1]]") == 2
    assert grandy_and_child_html.count("[[../index.html#SPEC_2]]") == 2
    assert grandy_and_child_html.count("@enduml") == 1
    assert "[[../index.html#STORY_1.1]]" not in grandy_and_child_html
    assert "[[../index.html#STORY_1.2]]" not in grandy_and_child_html
    assert "[[../index.html#STORY_2]]" not in grandy_and_child_html
    assert "[[../index.html#STORY_2.3]]" not in grandy_and_child_html
    assert "[[../index.html#SPEC_3]]" not in grandy_and_child_html
    assert "[[../index.html#SPEC_4]]" not in grandy_and_child_html
    assert "[[../index.html#STORY_3]]" not in grandy_and_child_html
    assert "[[../index.html#SPEC_5]]" not in grandy_and_child_html
