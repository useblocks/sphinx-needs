import os
import re
from pathlib import Path, PurePosixPath

import pytest
from lxml import html as html_parser
from sphinx import version_info
from sphinx.config import Config
from sphinx.util.console import strip_colors

#: A ``conf.py`` for the inline source projects below.
#: The id regex is relaxed, so that ids exercising the entity name sanitisation
#: (see :func:`~sphinx_needs.directives.needflow._plantuml.make_entity_names`) are allowed.
CONF_PY = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
needs_id_regex = "^[A-Z0-9_=-]+$"
needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "style": "node",
    },
]
"""


#: The graphviz outline color attribute, i.e. ``color`` but not ``fillcolor``.
_OUTLINE_COLOR = re.compile(r'(?<!fill)color="([^"]*)"')


def _outline_colors(source: str) -> list[str]:
    """Return every graphviz outline color in a diagram source.

    :param source: The generated graphviz source.
    :return: The value of each ``color`` attribute, in order of appearance.
    """
    return _OUTLINE_COLOR.findall(source)


def _debug_source(outdir: Path, file: str, index: int = 0) -> str:
    """Return the diagram source emitted by the needflow ``:debug:`` option.

    Both engines render it inside a ``<pre>``, but only graphviz syntax highlights
    it, so the text content is taken rather than the markup.

    :param outdir: The build output directory.
    :param file: The name of the built HTML page holding the needflow.
    :param index: The position of the needflow on the page.
    :return: The text of the requested ``<pre>`` block.
    """
    tree = html_parser.parse(outdir / file)
    return tree.xpath("//pre")[index].text_content()


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
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()

    warnings = (
        strip_colors(app._warning.getvalue())
        .replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
        .strip()
    )
    assert warnings == ""

    outdir = Path(app.outdir)

    svg = _get_svg(app.config, outdir, "index.html", "needflow-index-0")

    if test_app.config.needs_flow_engine == "graphviz" and version_info < (7, 2):
        pass  # links will be wrong due to https://github.com/sphinx-doc/sphinx/pull/11078
    elif test_app.config.needs_flow_engine == "graphviz" and os.name == "nt":
        pass  # TODO windows have // in links
    else:
        for link in (
            '"../index.html#SPEC_1"',
            '"../index.html#SPEC_2"',
            '"../index.html#STORY_1"',
            '"../index.html#STORY_1.1"',
            '"../index.html#STORY_1.2"',
            '"../index.html#STORY_1.subspec"',
            '"../index.html#STORY_2"',
            '"../index.html#STORY_2.another_one"',
        ):
            assert link in svg

    assert "No needs passed the filters" in Path(app.outdir, "index.html").read_text()

    svg = _get_svg(app.config, outdir, "page.html", "needflow-page-0")

    if test_app.config.needs_flow_engine == "graphviz" and version_info < (7, 2):
        pass  # links will be wrong due to https://github.com/sphinx-doc/sphinx/pull/11078
    elif test_app.config.needs_flow_engine == "graphviz" and os.name == "nt":
        pass  # TODO windows have // in links
    else:
        for link in (
            '"../index.html#SPEC_1"',
            '"../index.html#SPEC_2"',
            '"../index.html#STORY_1"',
            '"../index.html#STORY_1.1"',
            '"../index.html#STORY_1.2"',
            '"../index.html#STORY_1.subspec"',
            '"../index.html#STORY_2"',
            '"../index.html#STORY_2.another_one"',
        ):
            assert link in svg

    svg = _get_svg(
        app.config,
        outdir,
        "needflow_with_root_id.html",
        "needflow-needflow_with_root_id-0",
    )

    for link in ("SPEC_1", "STORY_1", "STORY_2"):
        assert link in svg

    assert "SPEC_2" not in svg

    empty_needflow_with_debug = Path(
        app.outdir, "empty_needflow_with_debug.html"
    ).read_text()
    assert "No needs passed the filters" in empty_needflow_with_debug


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needflow_incl_child_needs",
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needflow_incl_child_needs",
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_doc_build_needflow_incl_child_needs(test_app):
    app = test_app
    app.build()

    warnings = (
        strip_colors(app._warning.getvalue())
        .replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
        .strip()
    )
    assert warnings == ""

    outdir = Path(app.outdir)

    svg = _get_svg(app.config, outdir, "index.html", "needflow-index-0")

    if test_app.config.needs_flow_engine == "graphviz" and version_info < (7, 2):
        pass  # links will be wrong due to https://github.com/sphinx-doc/sphinx/pull/11078
    elif test_app.config.needs_flow_engine == "graphviz" and os.name == "nt":
        pass  # TODO windows have // in links
    else:
        for link in (
            '"../index.html#STORY_1"',
            '"../index.html#STORY_1.1"',
            '"../index.html#STORY_1.2"',
            '"../index.html#STORY_2"',
            '"../index.html#STORY_2.3"',
            '"../index.html#SPEC_1"',
            '"../index.html#SPEC_2"',
            '"../index.html#SPEC_3"',
            '"../index.html#SPEC_4"',
            '"../index.html#STORY_3"',
            '"../index.html#SPEC_5"',
        ):
            assert link in svg

        svg = _get_svg(
            app.config,
            outdir,
            "single_parent_need_filer.html",
            "needflow-single_parent_need_filer-0",
        )

        assert '"../index.html#STORY_3"' in svg
        for link in (
            '"../index.html#STORY_1"',
            '"../index.html#STORY_1.1"',
            '"../index.html#STORY_1.2"',
            '"../index.html#STORY_2"',
            '"../index.html#STORY_2.3"',
            '"../index.html#SPEC_1"',
            '"../index.html#SPEC_2"',
            '"../index.html#SPEC_3"',
            '"../index.html#SPEC_4"',
            '"../index.html#SPEC_5"',
        ):
            assert link not in svg

        svg = _get_svg(
            app.config,
            outdir,
            "single_child_with_child_need_filter.html",
            "needflow-single_child_with_child_need_filter-0",
        )

        assert '"../index.html#STORY_2"' in svg
        for link in (
            '"../index.html#STORY_1"',
            '"../index.html#STORY_1.1"',
            '"../index.html#STORY_1.2"',
            '"../index.html#STORY_2.3"',
            '"../index.html#SPEC_1"',
            '"../index.html#SPEC_2"',
            '"../index.html#SPEC_3"',
            '"../index.html#SPEC_4"',
            '"../index.html#STORY_3"',
            '"../index.html#SPEC_5"',
        ):
            assert link not in svg

        svg = _get_svg(
            app.config,
            outdir,
            "single_child_need_filter.html",
            "needflow-single_child_need_filter-0",
        )
        assert '"../index.html#SPEC_1"' in svg
        for link in (
            '"../index.html#STORY_1"',
            '"../index.html#STORY_1.1"',
            '"../index.html#STORY_1.2"',
            '"../index.html#STORY_2"',
            '"../index.html#STORY_2.3"',
            '"../index.html#SPEC_2"',
            '"../index.html#SPEC_3"',
            '"../index.html#SPEC_4"',
            '"../index.html#STORY_3"',
            '"../index.html#SPEC_5"',
        ):
            assert link not in svg

        svg = _get_svg(
            app.config, outdir, "grandy_and_child.html", "needflow-grandy_and_child-0"
        )
        for link in (
            '"../index.html#STORY_1"',
            '"../index.html#SPEC_1"',
            '"../index.html#SPEC_2"',
        ):
            assert link in svg
        for link in (
            '"../index.html#STORY_1.1"',
            '"../index.html#STORY_1.2"',
            '"../index.html#STORY_2"',
            '"../index.html#STORY_2.3"',
            '"../index.html#SPEC_3"',
            '"../index.html#SPEC_4"',
            '"../index.html#STORY_3"',
            '"../index.html#SPEC_5"',
        ):
            assert link not in svg


COLLIDING_IDS = """\
Colliding need ids
==================

.. spec:: First
   :id: R-1

.. spec:: Second
   :id: R=1
   :links: R-1

.. needflow::
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), COLLIDING_IDS)],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), COLLIDING_IDS)],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_node_ids_are_injective(test_app):
    """Needs whose ids sanitise alike must still be drawn as two nodes.

    PlantUML entity names cannot contain punctuation, so ``R-1`` and ``R=1`` both
    fold to ``R_1`` and used to collapse into a single node, silently losing a need
    and its edge. Graphviz quotes its ids and is immune, which is asserted here too,
    so both engines are pinned to the same "ids are stable and injective" policy.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    debug = _debug_source(Path(app.outdir), "index.html")

    if app.config.needs_flow_engine == "plantuml":
        # the ids are mapped in sorted order, so "R-1" keeps the plain name
        # and "R=1" is disambiguated with a numeric suffix
        assert debug.count("as R_1 ") == 1
        assert debug.count("as R_1_2 ") == 1
        assert "R_1_2 --> R_1" in debug
    else:
        assert debug.count('"R-1" [label=') == 1
        assert debug.count('"R=1" [label=') == 1
        assert '"R=1" -> "R-1" [' in debug


BORDER_COLORS = """\
Border colors
=============

.. spec:: Parent
   :id: PARENT

   .. spec:: Child
      :id: CHILD

.. needflow::
   :border_color: FF0000
   :debug:

.. needflow::
   :border_color: #00FF00
   :debug:

.. needflow::
   :border_color: [status == 'nonexistent']:0000FF
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), BORDER_COLORS)],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), BORDER_COLORS)],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_border_color_handling(test_app):
    """``:border_color:`` accepts an optional leading ``#`` and may resolve to nothing.

    Each engine has its own syntax for an outline color, so the option value is
    normalised before either adds its own prefix -- previously a value written with
    a ``#`` produced ``##RRGGBB`` (graphviz) or ``line:#RRGGBB`` (plantuml), and a
    variant expression matching nothing produced the literal color ``#None``
    (graphviz only).

    The project deliberately holds a need with a child, so that both graphviz node
    paths -- the plain node and the subgraph -- are covered and must agree.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    outdir = Path(app.outdir)
    bare = _debug_source(outdir, "index.html", 0)
    prefixed = _debug_source(outdir, "index.html", 1)
    unmatched = _debug_source(outdir, "index.html", 2)

    if app.config.needs_flow_engine == "plantuml":
        assert bare.count("line:FF0000") == 2
        assert prefixed.count("line:00FF00") == 2
        assert "line:#00FF00" not in prefixed
        assert "line:" not in unmatched
    else:
        # once for the subgraph (the parent) and once for the plain node (the child),
        # so the two graphviz node paths are pinned to the same handling
        assert _outline_colors(bare) == ["#FF0000", "#FF0000"]
        assert _outline_colors(prefixed) == ["#00FF00", "#00FF00"]
        assert "##00FF00" not in prefixed
        assert _outline_colors(unmatched) == []
        assert "#None" not in unmatched


HIGHLIGHT_WITH_NEEDS = """\
Highlight consulting other needs
================================

.. spec:: Parent
   :id: PARENT

   .. spec:: Child
      :id: CHILD

.. needflow::
   :highlight: len(needs) > 1
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), HIGHLIGHT_WITH_NEEDS),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), HIGHLIGHT_WITH_NEEDS),
            ],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_highlight_can_consult_other_needs(test_app):
    """A ``:highlight:`` filter sees all needs, whether or not a need has children.

    The graphviz subgraph path (taken by a need with parts or children) used to
    evaluate the filter without the needs list, so an expression referencing
    ``needs`` behaved differently -- here it would fail the whole build -- for a
    parent need than for a leaf one.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    debug = _debug_source(Path(app.outdir), "index.html")

    if app.config.needs_flow_engine == "plantuml":
        assert debug.count("line:FF0000") == 2
    else:
        # the parent is a subgraph and the child a plain node
        assert "  color=red;" in debug
        assert ", color=red]" in debug


UNKNOWN_CONFIG = """\
Unknown config
==============

.. spec:: A
   :id: AAAAA

.. needflow::
   :config: nonexistent_cfg
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), UNKNOWN_CONFIG)],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), UNKNOWN_CONFIG)],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_unknown_config_names_its_config_value(test_app):
    """An unknown ``:config:`` name must point at the config value that holds them.

    Each engine reads its own config value, and the plantuml message used to
    misspell it as ``need_flows_configs``, which does not exist.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())

    if app.config.needs_flow_engine == "plantuml":
        assert "config key 'nonexistent_cfg' not in 'needs_flow_configs'" in warnings
    else:
        assert "config key 'nonexistent_cfg' not in 'needs_graphviz_styles'" in warnings
    assert "need_flows_configs" not in warnings


UNKNOWN_LINK_TYPE = """\
Unknown link type
=================

.. spec:: A
   :id: AAAAA

.. needflow::
   :link_types: bogus_lt
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), UNKNOWN_LINK_TYPE),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), UNKNOWN_LINK_TYPE),
            ],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_unknown_link_type_warning_has_a_location(test_app):
    """The unknown link type warning must say which needflow it came from.

    The graphviz engine passed no location, so the warning arrived without the
    ``file:line`` of the directive that caused it.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).replace(
        str(app.srcdir) + os.path.sep, "<srcdir>/"
    )

    assert re.search(
        r"<srcdir>/index\.rst:\d+: WARNING: Unknown link type BOGUS_LT", warnings
    )


ALT_TEXTS = """\
Alt texts
=========

.. spec:: A
   :id: AAAAA

.. needflow::

.. needflow::
   :alt: my alt text

.. needflow::
   :alt:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), ALT_TEXTS)],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        }
    ],
    indirect=True,
)
def test_graphviz_alt_text(test_app):
    """A graphviz needflow gets a placeholder ``alt``, unless the author sets one.

    The directive always stored an ``alt``, so the intended placeholder default was
    unreachable and every image was published with an empty ``alt``. An explicitly
    empty ``:alt:`` still means "no alternative text", for a decorative diagram.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    tree = html_parser.parse(Path(app.outdir) / "index.html")
    alts = [img.attrib["alt"] for img in tree.xpath("//img[@class='graphviz']")]

    assert alts == ["needflow graphviz diagram", "my alt text", ""]


def test_get_entity_name_unmapped_id_falls_back_with_warning():
    """An unmapped id must degrade to a direct conversion, loudly, never crash.

    Every rendered need is mapped up front, so an unmapped id means an emission site
    bypassed the diagram's injective mapping; the lookup falls back to the (possibly
    colliding) direct conversion and warns. The two ``warnings == ""`` build tests
    above prove the fallback is unreachable today; this pins its contract directly.

    The capture handler is attached to the module's own logger rather than relying on
    propagation, which Sphinx disables once an application has configured logging.
    """
    import logging

    from sphinx_needs.directives.needflow._plantuml import get_entity_name

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    module_logger = logging.getLogger(
        "sphinx.sphinx_needs.directives.needflow._plantuml"
    )
    handler = _Capture(level=logging.WARNING)
    module_logger.addHandler(handler)
    old_level = module_logger.level
    module_logger.setLevel(logging.WARNING)
    try:
        assert get_entity_name({"R-1": "R_1", "R=1": "R_1_2"}, "R=1") == "R_1_2"
        assert records == []

        assert get_entity_name({}, "R=1") == "R_1"
        assert any(
            "'R=1' was not mapped to a plantuml entity name" in record.getMessage()
            for record in records
        )
    finally:
        module_logger.removeHandler(handler)
        module_logger.setLevel(old_level)


ENTITY_IN_TITLE = """\
Entity in a wrapped title
=========================

.. spec:: A "quoted" and <angled> title that wraps
   :id: AAAAA

.. needflow::
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), ENTITY_IN_TITLE)],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        }
    ],
    indirect=True,
)
def test_graphviz_label_does_not_break_html_entities(test_app):
    """A title holding a quote or a bracket must survive being wrapped.

    The label was escaped and then wrapped, so the wrapper counted the characters of an
    entity and could break inside one -- producing ``&quo<br/>t;``, which is invalid
    markup and a visibly broken label. Wrapping first also makes the wrap width count
    what the reader sees rather than what the escaper wrote.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    debug = _debug_source(Path(app.outdir), "index.html")

    assert "&quot;" in debug
    assert "&lt;angled&gt;" in debug
    # no entity may be interrupted by a line break element
    assert not re.search(r"&[a-z]*<br[^>]*>[a-z]*;", debug)


CLASS_AND_DEBUG = """\
Class and debug
===============

.. spec:: A
   :id: AAAAA

.. needflow::
   :class: my-flow-class
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), CLASS_AND_DEBUG),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), CLASS_AND_DEBUG),
            ],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_debug_is_a_literal_block_on_both_engines(test_app):
    """``:debug:`` must produce the same kind of block whichever engine draws.

    It emitted raw HTML on plantuml and a literal block on graphviz, so the same
    option gave the source line numbers and the theme's code styling on one engine
    only. Both now emit a literal block.

    ``:class:`` is pinned alongside it, because neither engine sets it deliberately:
    plantuml gets it only because docutils copies the classes of a replaced node onto
    the first node replacing it, which happens to be the figure, and graphviz writes
    it on the image instead. Both honour the option, in different places.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    tree = html_parser.parse(Path(app.outdir) / "index.html")
    if app.config.needs_flow_engine == "plantuml":
        assert tree.xpath("//figure[contains(@class, 'my-flow-class')]")
    else:
        assert tree.xpath("//img[contains(@class, 'my-flow-class')]")

    # a literal block, i.e. inside a highlight container, on either engine
    blocks = tree.xpath(
        "//div[contains(concat(' ', normalize-space(@class), ' '), ' highlight ')]//pre"
    )
    assert len(blocks) == 1
    assert "AAAAA" in blocks[0].text_content()
