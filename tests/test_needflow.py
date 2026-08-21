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


MALFORMED_GRAPHVIZ_STYLE = """\
Malformed graphviz style
========================

.. spec:: A
   :id: AAAAA

.. needflow::
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), MALFORMED_GRAPHVIZ_STYLE),
            ],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
                "needs_graphviz_styles": {"default": "not-a-mapping"},
            },
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), MALFORMED_GRAPHVIZ_STYLE),
            ],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
                "needs_graphviz_styles": {"default": {"node": "not-a-mapping"}},
            },
        },
    ],
    ids=["entry", "element"],
    indirect=True,
)
def test_malformed_graphviz_style_warns_instead_of_crashing(test_app):
    """A graphviz style that is not a mapping must not fail the whole build.

    An element type holding something other than a mapping of attributes travelled
    unchecked from the configuration into the emitter, where
    ``'str' object has no attribute 'items'`` aborted the build with a traceback
    instead of a message. Both shapes are now rejected where they are read, and the
    diagram is drawn without the offending style.
    """
    app = test_app
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "malformed config 'default' in 'needs_graphviz_styles'" in warnings

    assert "AAAAA" in _get_svg(
        app.config, Path(app.outdir), "index.html", "needflow-index-0"
    )


INVALID_ENGINE = """\
Invalid engine
==============

.. spec:: A
   :id: AAAAA

.. needflow::

.. needflow::
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), INVALID_ENGINE),
            ],
            "confoverrides": {"needs_flow_engine": "nosuchengine"},
        }
    ],
    indirect=True,
)
def test_invalid_flow_engine_warns_and_falls_back(test_app):
    """An unknown ``needs_flow_engine`` must warn, not end the build.

    The value used to trip a bare ``assert``, which reports a traceback rather than a
    message -- and which ``python -O`` strips altogether, leaving the unknown name to
    fail somewhere further downstream. The default engine draws the diagram instead.
    """
    app = test_app
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "unknown 'needs_flow_engine' value 'nosuchengine'" in warnings
    assert "'plantuml'" in warnings
    # said once for the project, not once per diagram
    assert warnings.count("unknown 'needs_flow_engine' value") == 1

    # the fallback engine still drew a diagram, rather than the build ending
    assert "needflow-index-0" in Path(app.outdir, "index.html").read_text()


SHARED_GRAPHVIZ_STYLE = """\
Shared graphviz style
=====================

.. spec:: A
   :id: AAAAA

.. needflow::
   :config: lefttoright,transparent
   :debug:

.. needflow::
   :config: lefttoright
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), SHARED_GRAPHVIZ_STYLE),
            ],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        }
    ],
    indirect=True,
)
def test_merging_configs_does_not_leak_into_the_next_diagram(test_app):
    """Naming several ``:config:`` styles must not edit the styles themselves.

    The merge took the first style's attributes by reference and then updated that
    same dictionary with the second style's, so the configured (and built-in) styles
    were rewritten in place: every later diagram naming ``lefttoright`` inherited the
    ``transparent`` background of the diagram before it, for the rest of the build.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    outdir = Path(app.outdir)
    merged = _debug_source(outdir, "index.html", 0)
    plain = _debug_source(outdir, "index.html", 1)

    assert 'rankdir="LR"' in merged
    assert 'bgcolor="transparent"' in merged

    assert 'rankdir="LR"' in plain
    assert 'bgcolor="transparent"' not in plain


DIRECTION_DOC = """\
Direction
=========

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :direction: {value}
   :debug:
"""


@pytest.mark.parametrize(
    "value,plantuml_statement,rankdir",
    [
        ("down", None, None),
        ("tb", None, None),
        ("td", None, None),
        ("right", "left to right direction", "LR"),
        ("lr", "left to right direction", "LR"),
        # PlantUML degrades `up` to its axis mate `down`, which is how it already draws,
        # so the degraded diagram emits nothing at all -- byte-identical to the default
        ("up", None, "BT"),
        ("bt", None, "BT"),
        ("left", "left to right direction", "RL"),
        ("rl", "left to right direction", "RL"),
    ],
)
@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
def test_direction_option_per_engine(
    make_app,
    tmp_path,
    plantuml_command,
    engine,
    value,
    plantuml_statement,
    rankdir,
):
    """Every accepted ``:direction:`` spelling reaches both engines.

    PlantUML has only ``top to bottom direction`` and ``left to right direction``, so a
    reversed direction is drawn by its axis mate; Graphviz draws all four with
    ``rankdir``. ``down`` and its aliases must emit *nothing at all*, because a diagram
    already drawn that way must keep the source it had before the option existed.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(DIRECTION_DOC.format(value=value), "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "graphviz_output_format": "svg",
            "needs_flow_engine": engine,
        },
    )
    app.build()

    source = _debug_source(Path(app.outdir), "index.html")
    if engine == "plantuml":
        assert ("' Direction" in source) is (plantuml_statement is not None)
        if plantuml_statement is not None:
            assert plantuml_statement in source
    else:
        assert ("rankdir=" in source) is (rankdir is not None)
        if rankdir is not None:
            assert f'rankdir="{rankdir}"' in source


@pytest.mark.parametrize(
    "value,warned",
    [("up", "'up'"), ("bt", "'up'"), ("left", "'left'"), ("rl", "'left'")],
)
def test_plantuml_reports_the_direction_it_cannot_draw(
    make_app, tmp_path, plantuml_command, value, warned
):
    """A direction PlantUML has no primitive for degrades with one warning per project.

    ``bottom to top direction`` and ``right to left direction`` are syntax errors for
    PlantUML (probed against 1.2020.02), so the axis mate is drawn instead. That is a
    named intent going unhonoured rather than a decorative substitution, so it is
    reported -- but once for the whole project, not once per diagram.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(
        DIRECTION_DOC.format(value=value)
        + f"\n.. needflow::\n   :direction: {value}\n",
        "utf8",
    )

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert f"the plantuml engine cannot draw {warned}" in warnings
    # two diagrams ask for it, and the project is told once
    assert warnings.count("the plantuml engine cannot draw") == 1


def test_graphviz_draws_every_direction_without_warning(
    make_app, tmp_path, plantuml_command
):
    """Graphviz supports all four directions, so none of them may warn.

    The companion of the PlantUML degradation test: a tier-2 warning that fired on an
    engine which *can* draw the direction would be noise, and would make an author
    change a diagram that was already right.
    """
    document = "Directions\n==========\n\n.. spec:: A\n   :id: AAAAA\n\n"
    for value in ("down", "up", "right", "left"):
        document += f".. needflow::\n   :direction: {value}\n\n"
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(document, "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "graphviz_output_format": "svg",
            "needs_flow_engine": "graphviz",
        },
    )
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""


def test_unknown_direction_is_rejected_as_the_option_is_parsed(
    make_app, tmp_path, plantuml_command
):
    """``:direction:`` is a closed enumeration, so docutils reports a bad value.

    A layout nobody can draw is a mistake in the document rather than a degradation, and
    docutils already reports it against the directive with the accepted values listed.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(DIRECTION_DOC.format(value="sideways"), "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    # docutils' own `choice` message, which lists what the option accepts
    assert '"sideways" unknown; choose from' in warnings
    for accepted in ("down", "up", "right", "left", "tb", "td", "bt", "lr", "rl"):
        assert f'"{accepted}"' in warnings


CONFIG_DIRECTION_DOC = """\
Config direction
================

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :config: {config}
   :direction: {value}
   :debug:
"""


@pytest.mark.parametrize(
    "engine,config_name,emitted,overridden",
    [
        (
            "plantuml",
            "lefttoright",
            "top to bottom direction",
            "left to right direction",
        ),
        ("graphviz", "lefttoright", 'rankdir="TB"', 'rankdir="LR"'),
    ],
)
def test_explicit_direction_beats_the_engine_config(
    make_app, tmp_path, plantuml_command, engine, config_name, emitted, overridden
):
    """An explicit ``:direction:`` must win over the config blob written beside it.

    The blob is a preamble of defaults and the option a per-element value, which is the
    precedence both engines already give them -- but a *default* direction has to be
    restated to win, because emitting nothing would leave the blob's layout standing.
    The emitted source is asserted, so the test cannot pass on the warning alone.

    *Where* it is restated is asserted too, because on both engines the later statement
    is the one that takes effect: a ``rankdir`` written before the blob's ``graph [...]``
    block -- which is where the shipped ``lefttoright`` config puts its own -- would be
    emitted, matched by a containment check, and then overridden by the very blob it was
    supposed to beat.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(
        CONFIG_DIRECTION_DOC.format(config=config_name, value="down"), "utf8"
    )

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "graphviz_output_format": "svg",
            "needs_flow_engine": engine,
        },
    )
    app.build()

    source = _debug_source(Path(app.outdir), "index.html")
    assert emitted in source
    # the option's statement must come after the blob's, or the blob wins at render time
    assert source.index(emitted) > source.index(overridden)

    warnings = strip_colors(app._warning.getvalue())
    assert "disagrees with the direction 'down'" in warnings


@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
def test_agreeing_engine_config_does_not_warn_or_restate(
    make_app, tmp_path, plantuml_command, engine
):
    """A config blob that already draws the asked-for direction is left alone.

    Nothing disagrees, so nothing is reported; and the direction is already in force, so
    restating it would move the bytes of a diagram whose author changed nothing.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(
        CONFIG_DIRECTION_DOC.format(config="lefttoright", value="right"), "utf8"
    )

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "graphviz_output_format": "svg",
            "needs_flow_engine": engine,
        },
    )
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""

    source = _debug_source(Path(app.outdir), "index.html")
    if engine == "plantuml":
        assert "' Direction" not in source
        assert source.count("left to right direction") == 1
    else:
        # the blob's own `rankdir` stands, and no second one is written after it
        assert source.count("rankdir=") == 1


def test_project_direction_default_applies_without_the_option(
    make_app, tmp_path, plantuml_command
):
    """``needs_flow_direction`` is the default a diagram without the option gets."""
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(
        "Default\n=======\n\n.. spec:: A\n   :id: AAAAA\n\n.. needflow::\n   :debug:\n",
        "utf8",
    )

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_direction": "right",
        },
    )
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""
    assert "left to right direction" in _debug_source(Path(app.outdir), "index.html")


def test_option_beats_the_project_direction_default(
    make_app, tmp_path, plantuml_command
):
    """A diagram always has the last word over ``needs_flow_direction``."""
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(DIRECTION_DOC.format(value="down"), "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_direction": "right",
        },
    )
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""
    source = _debug_source(Path(app.outdir), "index.html")
    assert "left to right direction" not in source
    assert "' Direction" not in source


NO_NEEDFLOW = """\
No needflow at all
==================

.. spec:: A
   :id: AAAAA
"""


def test_bad_flow_config_is_reported_without_any_needflow(
    make_app, tmp_path, plantuml_command
):
    """An unusable ``needs_flow_*`` value is reported where the configuration is read.

    Checking these as a diagram is drawn means a project that misconfigures one and
    happens to have no needflow anywhere is never told about it -- and then gets a
    different diagram the day somebody adds one.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(NO_NEEDFLOW, "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_direction": "sideways",
        },
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "Invalid 'needs_flow_direction' value 'sideways'" in warnings
    assert "allowed values: down, up, right, left" in warnings


def test_bad_flow_config_is_reported_once_not_once_per_diagram(
    make_app, tmp_path, plantuml_command
):
    """The read-time report is the only one, however many diagrams the project draws.

    The resolution falls back through the same validator, with the same message, so
    Sphinx's ``once`` filter collapses the two -- and the surviving warning is the one
    without a directive location, because a ``conf.py`` mistake must not be reported
    against whichever ``index.rst`` line happened to be drawn first.
    """
    document = "Two diagrams\n============\n\n.. spec:: A\n   :id: AAAAA\n\n"
    document += ".. needflow::\n\n.. needflow::\n"
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(document, "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_direction": "sideways",
        },
    )
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert warnings.count("Invalid 'needs_flow_direction' value") == 1
    # reported against the project, not against a line of the document
    assert "index.rst" not in warnings


NORMALISED_CONFIG = """\
Config value normalisation
==========================

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :debug:
"""


@pytest.mark.parametrize(
    "override,needle",
    [
        ({"needs_flow_direction": "  RIGHT  "}, "left to right direction"),
        ({"needs_flow_engine": "  GraphViz  "}, "digraph needflow"),
    ],
    ids=["direction", "engine"],
)
def test_enum_config_values_ignore_case_and_padding(
    make_app, tmp_path, plantuml_command, override, needle
):
    """A configured enum value is matched the way the matching option value is.

    The directive options go through docutils' ``choice``, which lowercases and strips
    before matching, so ``:engine: PlantUML`` has always been accepted. The configuration
    side matched exactly, so the same word in ``conf.py`` warned and fell back --
    silently drawing something else.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(NORMALISED_CONFIG, "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "graphviz_output_format": "svg",
            **override,
        },
    )
    app.build()

    # the value is usable, so nothing is reported and nothing falls back
    assert strip_colors(app._warning.getvalue()).strip() == ""
    assert needle in _debug_source(Path(app.outdir), "index.html")


@pytest.mark.parametrize(
    "override,message",
    [
        ({"needs_flow_direction": "  sideways  "}, "Invalid 'needs_flow_direction'"),
        ({"needs_flow_engine": "  crayon  "}, "unknown 'needs_flow_engine'"),
    ],
    ids=["direction", "engine"],
)
def test_normalisation_does_not_silence_a_genuinely_wrong_value(
    make_app, tmp_path, plantuml_command, override, message
):
    """Tolerating case and padding must not turn a wrong value into a silent fallback.

    The point of normalising is to accept what the author plainly meant, not to accept
    anything -- so a value that is wrong after normalisation is still reported, and the
    message quotes what was actually written.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(NORMALISED_CONFIG, "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command, **override},
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert message in warnings
    # the author's own spelling is echoed, padding and all, so it can be found in conf.py
    assert repr(next(iter(override.values()))) in warnings


LINK_LABELS_DOC = """\
Link labels
===========

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :show_link_names:{value}
   :debug:
"""


@pytest.mark.parametrize(
    "written,label",
    [
        ("", "links outgoing"),
        (" outgoing", "links outgoing"),
        (" incoming", "links incoming"),
        (" type", "links"),
        (" none", None),
        # docutils' `choice` lowercases and strips, so these are the same values
        (" Incoming ", "links incoming"),
    ],
    ids=["bare", "outgoing", "incoming", "type", "none", "padded"],
)
@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
def test_show_link_names_takes_a_value(
    make_app, tmp_path, plantuml_command, engine, written, label
):
    """Each accepted ``:show_link_names:`` value labels edges with what it names.

    Written bare the option means ``outgoing``, which is exactly what the flag has
    always drawn -- the option is widened rather than replaced, so no existing document
    changes. ``none``, ``incoming`` and ``type`` are new: the flag could only ever say
    "outgoing", and could not say "off" at all.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(LINK_LABELS_DOC.format(value=written), "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "graphviz_output_format": "svg",
            "needs_flow_engine": engine,
        },
    )
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""

    source = _debug_source(Path(app.outdir), "index.html")
    # only the edges are inspected: a graphviz *node* always carries an HTML label
    edges = source.split(
        "Connection definition" if engine == "plantuml" else "edge definitions"
    )[-1]
    if label is None:
        # `none` must leave the edge bare, not label it with an empty string
        assert ": " not in edges
        assert "label=" not in edges
    elif engine == "plantuml":
        assert f": {label}\\n" in edges
    else:
        assert f'label="{label}"' in edges


def test_unknown_show_link_names_value_is_rejected_as_it_is_parsed(
    make_app, tmp_path, plantuml_command
):
    """``:show_link_names:`` is a closed enumeration once it takes a value."""
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(
        LINK_LABELS_DOC.format(value=" sideways"), "utf8"
    )

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert '"sideways" unknown; choose from' in warnings
    for accepted in ("none", "outgoing", "incoming", "type"):
        assert f'"{accepted}"' in warnings


@pytest.mark.parametrize(
    "configured,label",
    [
        (True, "links outgoing"),
        (False, None),
        ("outgoing", "links outgoing"),
        ("incoming", "links incoming"),
        ("type", "links"),
        ("none", None),
        ("  Type  ", "links"),
        # a value declared `bool` for years: a truthy non-boolean drew labels silently,
        # so it still does rather than being held to the enumeration
        (1, "links outgoing"),
        (0, None),
    ],
    ids=[
        "true",
        "false",
        "outgoing",
        "incoming",
        "type",
        "none",
        "padded",
        "truthy-int",
        "falsey-int",
    ],
)
def test_needs_flow_show_links_accepts_a_value_or_a_boolean(
    make_app, tmp_path, plantuml_command, configured, label
):
    """The project default takes a value, and keeps meaning what a boolean meant.

    ``True`` is the ``outgoing`` it has always drawn and ``False`` is ``none``. Anything
    that is neither a string nor a boolean is read for its truth, because that is what a
    value declared ``bool`` for years actually did.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(
        "Configured\n==========\n\n.. spec:: A\n   :id: AAAAA\n\n"
        ".. spec:: B\n   :id: BBBBB\n   :links: AAAAA\n\n.. needflow::\n   :debug:\n",
        "utf8",
    )

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_show_links": configured,
        },
    )
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""

    source = _debug_source(Path(app.outdir), "index.html")
    if label is None:
        assert ": " not in source.split("Connection definition")[-1]
    else:
        assert f": {label}\\n" in source


def test_unusable_needs_flow_show_links_string_warns_and_falls_back(
    make_app, tmp_path, plantuml_command
):
    """A *string* is someone naming a value, so it is held to the enumeration.

    This is the one input whose behaviour changes: a non-enumerated string used to be
    truthy and draw labels. It is reported where the configuration is read, once.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(NO_NEEDFLOW, "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_show_links": "yes please",
        },
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "Invalid 'needs_flow_show_links' value 'yes please'" in warnings
    assert "allowed values: none, outgoing, incoming, type" in warnings
    assert "'none' is used" in warnings


def test_show_link_names_option_beats_the_project_default(
    make_app, tmp_path, plantuml_command
):
    """A diagram has the last word, which it could not have before.

    The flag and the configuration used to be OR-ed, so a project that turned labels on
    left no way of drawing one unlabelled diagram.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(LINK_LABELS_DOC.format(value=" none"), "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_show_links": "outgoing",
        },
    )
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""
    source = _debug_source(Path(app.outdir), "index.html")
    assert "links outgoing" not in source


@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
def test_needgantt_and_needsequence_keep_their_bare_flag(
    make_app, tmp_path, plantuml_command, engine
):
    """The widened option must not narrow the flag the other diagrams share.

    ``show_link_names`` lives on the shared diagram data type, and needgantt and
    needsequence still take it as a bare flag, so needflow's value lands beside it.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(
        "Shared flag\n===========\n\n.. spec:: A\n   :id: AAAAA\n\n"
        ".. spec:: B\n   :id: BBBBB\n   :links: AAAAA\n\n"
        ".. needsequence::\n   :start: AAAAA\n   :show_link_names:\n\n"
        ".. needgantt::\n   :show_link_names:\n",
        "utf8",
    )

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "graphviz_output_format": "svg",
            "needs_flow_engine": engine,
        },
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "unknown option" not in warnings
    assert "no arguments allowed" not in warnings


LEGEND_CONF = (
    CONF_PY
    + """
needs_types.append(
    {
        "directive": "undrawn",
        "title": "Never Drawn",
        "prefix": "U_",
        "color": "#CCCCCC",
        "style": "node",
    }
)
needs_flow_legends = {
    "inside": {"parts": ["types"]},
    "beside": {"parts": ["types"], "placement": "external"},
    "links": {"parts": ["links"], "placement": "external"},
    "both": {"parts": ["types", "links"], "placement": "external"},
    "reversed": {"parts": ["links", "types"], "placement": "external"},
}
"""
)

LEGEND_DOC = """\
Legend
======

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :show_legend:{value}
   :debug:
"""


def _legend_sections(outdir: Path, file: str = "index.html") -> list[str]:
    """The out-of-diagram legend sections rendered on a page, in document order.

    :param outdir: The build output directory.
    :param file: The page holding the needflow.
    :return: The section name of each rendered legend table, in order.
    """
    tree = html_parser.parse(outdir / file)
    tables = tree.xpath(
        "//table[contains(concat(' ', normalize-space(@class), ' '),"
        " ' needflow_legend_table ')]"
    )
    sections = []
    for table in tables:
        classes = str(table.get("class", "")).split()
        for part in ("types", "links"):
            if f"needflow_legend_{part}" in classes:
                sections.append(part)
    return sections


def _legend_rows(outdir: Path, part: str, file: str = "index.html") -> list[str]:
    """The label column of one rendered legend section.

    :param outdir: The build output directory.
    :param part: The section to read, ``types`` or ``links``.
    :param file: The page holding the needflow.
    :return: The label of each row, in order.
    """
    tree = html_parser.parse(outdir / file)
    column = 2 if part == "types" else 1
    tables = tree.xpath(
        "//table[contains(concat(' ', normalize-space(@class), ' '),"
        f" ' needflow_legend_{part} ')]"
    )
    assert len(tables) == 1, f"expected one {part!r} legend table, got {len(tables)}"
    return [
        cell.text_content().strip()
        for cell in tables[0].xpath(f".//tbody/tr/td[{column}]")
    ]


def _build_legend(make_app, tmp_path, plantuml_command, engine, written, **overrides):
    """Build the legend project with one ``:show_legend:`` spelling.

    :param engine: The needflow engine to draw with.
    :param written: What to write after ``:show_legend:``, empty for a bare option.
    :param overrides: Extra configuration overrides.
    :return: The built application.
    """
    (tmp_path / "conf.py").write_text(LEGEND_CONF, "utf8")
    (tmp_path / "index.rst").write_text(LEGEND_DOC.format(value=written), "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "graphviz_output_format": "svg",
            "needs_flow_engine": engine,
            **overrides,
        },
    )
    app.build()
    return app


@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
def test_bare_show_legend_still_draws_the_in_diagram_legend(
    make_app, tmp_path, plantuml_command, engine
):
    """A bare ``:show_legend:`` must draw exactly the legend it always drew.

    The option is widened to take a key, not replaced, so a document written before
    keys existed keeps its in-image legend -- including the long-standing difference
    that plantuml lists every configured type while graphviz lists only what it drew.
    """
    app = _build_legend(make_app, tmp_path, plantuml_command, engine, "")

    assert strip_colors(app._warning.getvalue()).strip() == ""

    source = _debug_source(Path(app.outdir), "index.html")
    if engine == "plantuml":
        assert "' Legend definition" in source
        # every configured type, drawn or not
        assert "Never Drawn" in source
    else:
        assert "<B>Legend</B>" in source
        assert "Never Drawn" not in source

    # and nothing beside the diagram
    assert _legend_sections(Path(app.outdir)) == []


@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
def test_show_legend_key_selects_a_configured_legend(
    make_app, tmp_path, plantuml_command, engine
):
    """A named legend renders the same table beside the diagram on either engine.

    An external legend lists only what the diagram actually drew, which is the scope
    rule the two in-image legends disagree about.
    """
    app = _build_legend(make_app, tmp_path, plantuml_command, engine, " beside")

    assert strip_colors(app._warning.getvalue()).strip() == ""

    outdir = Path(app.outdir)
    assert _legend_sections(outdir) == ["types"]
    assert _legend_rows(outdir, "types") == ["Specification"]

    # the in-diagram legend is not drawn as well
    source = _debug_source(outdir, "index.html")
    assert "' Legend definition" not in source
    assert "<B>Legend</B>" not in source


@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
def test_show_legend_can_describe_link_types(
    make_app, tmp_path, plantuml_command, engine
):
    """A link legend describes the link types the diagram drew edges for.

    No in-diagram legend here can do this, so a legend asking for links is always
    drawn beside the diagram.
    """
    app = _build_legend(make_app, tmp_path, plantuml_command, engine, " links")

    assert strip_colors(app._warning.getvalue()).strip() == ""

    outdir = Path(app.outdir)
    assert _legend_sections(outdir) == ["links"]
    assert _legend_rows(outdir, "links") == ["links"]


@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
@pytest.mark.parametrize(
    "key,expected",
    [(" both", ["types", "links"]), (" reversed", ["links", "types"])],
    ids=["both", "reversed"],
)
def test_legend_sections_keep_their_configured_order(
    make_app, tmp_path, plantuml_command, engine, key, expected
):
    """``parts`` is an ordered list, and the order is contract.

    A reader scanning two diagrams should find the same section in the same place, so
    ``["links", "types"]`` puts links first and keeps it there. A tool treating ``parts``
    as a set, or as an enum with a fixed section order, renders these the same way round
    and fails one of the two.
    """
    app = _build_legend(make_app, tmp_path, plantuml_command, engine, key)

    assert strip_colors(app._warning.getvalue()).strip() == ""
    assert _legend_sections(Path(app.outdir)) == expected


@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
def test_internal_placement_that_cannot_be_honoured_degrades_silently(
    make_app, tmp_path, plantuml_command, engine
):
    """A legend asking for links inside the diagram gets the table instead, silently.

    Neither in-image legend here can describe link types, so the preference cannot be
    met; the two legends carry identical information and differ only in where they sit,
    so the substitution is decorative rather than an intent gone unhonoured.
    """
    (tmp_path / "conf.py").write_text(
        LEGEND_CONF
        + '\nneeds_flow_legends["inside"] = {"parts": ["types", "links"]}\n',
        "utf8",
    )
    (tmp_path / "index.rst").write_text(LEGEND_DOC.format(value=" inside"), "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "graphviz_output_format": "svg",
            "needs_flow_engine": engine,
        },
    )
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""
    assert _legend_sections(Path(app.outdir)) == ["types", "links"]


def test_needs_flow_show_legend_supplies_the_key(make_app, tmp_path, plantuml_command):
    """``needs_flow_show_legend`` says *which* legend a bare option gets."""
    app = _build_legend(
        make_app,
        tmp_path,
        plantuml_command,
        "plantuml",
        "",
        needs_flow_show_legend="beside",
    )

    assert strip_colors(app._warning.getvalue()).strip() == ""
    assert _legend_sections(Path(app.outdir)) == ["types"]


def test_needs_flow_show_legend_never_says_whether(
    make_app, tmp_path, plantuml_command
):
    """A project default cannot give a legend to a diagram that never asked for one.

    Whether there is a legend stays with the directive; the configuration only ever
    says which one. There is deliberately no project-wide way of putting a legend on
    every diagram -- a legend describes one picture.
    """
    (tmp_path / "conf.py").write_text(LEGEND_CONF, "utf8")
    (tmp_path / "index.rst").write_text(
        "No legend\n=========\n\n.. spec:: A\n   :id: AAAAA\n\n.. needflow::\n   :debug:\n",
        "utf8",
    )
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_show_legend": "beside",
        },
    )
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""
    assert _legend_sections(Path(app.outdir)) == []
    assert "' Legend definition" not in _debug_source(Path(app.outdir), "index.html")


def test_option_key_beats_the_project_key(make_app, tmp_path, plantuml_command):
    """The directive's own key wins over ``needs_flow_show_legend``."""
    app = _build_legend(
        make_app,
        tmp_path,
        plantuml_command,
        "plantuml",
        " reversed",
        needs_flow_show_legend="beside",
    )

    assert strip_colors(app._warning.getvalue()).strip() == ""
    assert _legend_sections(Path(app.outdir)) == ["links", "types"]


def test_unknown_option_key_warns_and_hands_on_to_the_project_key(
    make_app, tmp_path, plantuml_command
):
    """An unknown option key is treated as unset, so the chain continues.

    A key that names nothing warns and then behaves as though it had not been written,
    which is the rule the rest of this vocabulary follows. A typo in one directive must
    not silently cost the project the legend it configured.
    """
    app = _build_legend(
        make_app,
        tmp_path,
        plantuml_command,
        "plantuml",
        " besidee",
        needs_flow_show_legend="reversed",
    )

    warnings = strip_colors(app._warning.getvalue())
    assert "legend key 'besidee' is not defined in 'needs_flow_legends'" in warnings
    assert "available: beside, both, inside, links, reversed" in warnings
    # ...and the project's own legend is still drawn
    assert _legend_sections(Path(app.outdir)) == ["links", "types"]


def test_unknown_option_key_falls_back_to_the_engine_legend(
    make_app, tmp_path, plantuml_command
):
    """With nothing configured either, the chain ends at the engine's own legend."""
    app = _build_legend(make_app, tmp_path, plantuml_command, "plantuml", " besidee")

    warnings = strip_colors(app._warning.getvalue())
    assert "legend key 'besidee' is not defined in 'needs_flow_legends'" in warnings
    assert _legend_sections(Path(app.outdir)) == []
    assert "' Legend definition" in _debug_source(Path(app.outdir), "index.html")


def test_unknown_option_key_is_reported_per_directive(
    make_app, tmp_path, plantuml_command
):
    """An option key is the directive's own text, so it is reported every time.

    The author can act on each one, and two diagrams with the same typo are two
    mistakes to fix.
    """
    (tmp_path / "conf.py").write_text(LEGEND_CONF, "utf8")
    (tmp_path / "index.rst").write_text(
        "Two typos\n=========\n\n.. spec:: A\n   :id: AAAAA\n\n"
        ".. needflow::\n   :show_legend: besidee\n\n"
        ".. needflow::\n   :show_legend: besidee\n",
        "utf8",
    )
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert warnings.count("legend key 'besidee' is not defined") == 2
    # reported against the directives, under the needflow subtype
    assert warnings.count("needs.needflow") == 2


def test_unknown_project_key_is_reported_once_for_the_project(
    make_app, tmp_path, plantuml_command
):
    """An unknown ``needs_flow_show_legend`` is one ``conf.py`` mistake, said once.

    Repeating it at every needflow would bury the directive-level warnings an author
    can act on, and reporting it against whichever ``index.rst`` line was drawn first
    would point at the wrong file altogether.
    """
    (tmp_path / "conf.py").write_text(LEGEND_CONF, "utf8")
    (tmp_path / "index.rst").write_text(
        "Two diagrams\n============\n\n.. spec:: A\n   :id: AAAAA\n\n"
        ".. needflow::\n   :show_legend:\n\n.. needflow::\n   :show_legend:\n",
        "utf8",
    )
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_show_legend": "besidee",
        },
    )
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    # said once, although two needflows asked for a legend
    assert warnings.count("legend key 'besidee'") == 1
    assert "of 'needs_flow_show_legend'" in warnings
    # a conf.py problem, so no directive location and the config subtype
    assert "needs.config" in warnings
    assert "index.rst" not in warnings


@pytest.mark.parametrize(
    "legends,message",
    [
        ({"bad": {"parts": 5}}, "'parts' of legend 'bad' must be a list"),
        ({"bad": {"parts": "both"}}, "'parts' of legend 'bad' must be a list"),
        ({"bad": {"parts": ["sideways"]}}, "unknown legend section 'sideways'"),
        ({"bad": {"placement": "nearby"}}, "unknown placement 'nearby'"),
        ({"bad": {"nonsense": 1}}, "unknown key(s) ['nonsense'] of legend 'bad'"),
        ({"bad": "types"}, "legend 'bad' in 'needs_flow_legends' must be a mapping"),
        ({" bad ": {}}, "can never be selected"),
        ({"": {}}, "can never be selected"),
    ],
    ids=[
        "parts-int",
        "parts-string",
        "unknown-section",
        "unknown-placement",
        "unknown-key",
        "not-a-mapping",
        "padded-name",
        "empty-name",
    ],
)
def test_unusable_legend_config_warns_and_never_crashes(
    make_app, tmp_path, plantuml_command, legends, message
):
    """A malformed ``needs_flow_legends`` entry is reported, and the build finishes.

    ``parts: 5`` is not the hypothetical it looks like: a number is not iterable and
    ended a build with a traceback, and a bare string iterates character by character,
    warning about single letters and then drawing the default legend anyway.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(LEGEND_DOC.format(value=" bad"), "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_legends": legends,
        },
    )
    app.build()  # must not raise

    assert message in strip_colors(app._warning.getvalue())


def test_unusable_legend_config_is_reported_without_any_needflow(
    make_app, tmp_path, plantuml_command
):
    """The legend configuration is checked where it is read, not where it is used."""
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(NO_NEEDFLOW, "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_legends": {"bad": {"parts": 5}},
            "needs_flow_show_legend": "nowhere",
        },
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "'parts' of legend 'bad' must be a list" in warnings
    assert "legend key 'nowhere' of 'needs_flow_show_legend'" in warnings


@pytest.mark.parametrize(
    "project_key,quoted",
    [(5, "'5'"), (None, "'None'"), (True, "'True'")],
    ids=["int", "none", "bool"],
)
def test_non_string_show_legend_key_is_reported_not_crashed(
    make_app, tmp_path, plantuml_command, project_key, quoted
):
    """A non-string ``needs_flow_show_legend`` must warn, not end the build.

    Its ``types: (str,)`` metadata makes Sphinx warn about the wrong type and then hand
    the raw value through, so one line of ``conf.py`` reached ``str.strip`` on an ``int``
    and killed the build with a traceback -- the very outcome the read-time validation
    exists to prevent, and which every sibling key already guards against.

    This is the read-time path, exercised with **no needflow anywhere**: the value is
    coerced, fails the key lookup, and is reported as any other unknown name would be.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(NO_NEEDFLOW, "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_show_legend": project_key,
        },
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert f"legend key {quoted} of 'needs_flow_show_legend' is not defined" in warnings


@pytest.mark.parametrize(
    "project_key,quoted",
    [(5, "'5'"), (None, "'None'"), (True, "'True'")],
    ids=["int", "none", "bool"],
)
def test_non_string_show_legend_key_still_resolves_the_chain(
    make_app, tmp_path, plantuml_command, project_key, quoted
):
    """The same value must not crash the *per-diagram* resolution either.

    The read-time check and the chain each read this value, so guarding only the first
    would move the crash to build time rather than remove it. Two needflows ask for a
    legend without naming one, so the chain reaches the project key both times: it is
    coerced, names nothing, and hands on to the engine's own legend -- which is drawn.

    The warning is emitted once for the build, not once per diagram: the read-time site
    and the chain produce the *same* text, which is what lets Sphinx's ``once`` filter
    collapse them onto the one without a directive location.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(
        "Two diagrams\n============\n\n.. spec:: A\n   :id: AAAAA\n\n"
        ".. needflow::\n   :show_legend:\n   :debug:\n\n"
        ".. needflow::\n   :show_legend:\n   :debug:\n",
        "utf8",
    )
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "plantuml": plantuml_command,
            "needs_flow_show_legend": project_key,
        },
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert f"legend key {quoted} of 'needs_flow_show_legend' is not defined" in warnings
    # said once for the project, although two needflows consulted it
    assert warnings.count(f"legend key {quoted}") == 1
    # a conf.py problem, so no directive location
    assert "index.rst" not in warnings

    # the chain handed on rather than being replaced: the engine drew its own legend
    outdir = Path(app.outdir)
    assert "' Legend definition" in _debug_source(outdir, "index.html")
    assert _legend_sections(outdir) == []


def test_a_legend_beside_a_plantuml_figure_keeps_the_directive_classes(
    make_app, tmp_path, plantuml_command
):
    """``:class:`` reaches the plantuml figure, which is where the option says it goes.

    The option was collected and then dropped by this engine, so the same option styled
    a graphviz diagram and did nothing to a plantuml one.
    """
    (tmp_path / "conf.py").write_text(LEGEND_CONF, "utf8")
    (tmp_path / "index.rst").write_text(
        "Classes\n=======\n\n.. spec:: A\n   :id: AAAAA\n\n"
        ".. needflow::\n   :class: my-flow\n   :show_legend: beside\n",
        "utf8",
    )
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()

    html = Path(app.outdir, "index.html").read_text()
    assert "my-flow" in html


#: A ``conf.py`` whose link type and need type use only the neutral styling keys.
NEUTRAL_CONF_PY = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "shape": "cylinder",
    },
]
needs_links = {
    "links": {
        "incoming": "is required by",
        "outgoing": "requires",
        "line": "dashed",
        "arrow": "circle",
        "color": "#00AA00",
    },
}
"""

NEUTRAL_LINKS = """\
Neutral link and type styling
=============================

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), NEUTRAL_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), NEUTRAL_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
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
def test_neutral_link_and_type_styling(test_app):
    """``needs_links[].line/arrow/color`` and ``needs_types[].shape`` reach both engines.

    The old keys held PlantUML tokens that graphviz had to translate through a lookup
    table with a documented "cheat", and ``color`` was carried by the configuration but
    honoured by neither engine. The neutral values say what is meant, and each engine
    writes it in its own syntax.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    debug = _debug_source(Path(app.outdir), "index.html")

    if app.config.needs_flow_engine == "plantuml":
        assert "database " in debug  # the neutral cylinder
        assert "[dashed,#00AA00]" in debug
        assert "-o " in debug  # the neutral circle head
    else:
        assert 'shape="cylinder"' in debug
        assert 'style="dashed"' in debug
        assert "arrowhead=odot" in debug
        assert 'color="#00AA00"' in debug


LEGACY_CONF_PY = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "style": "node",
    },
]
needs_links = {
    "links": {
        "incoming": "is required by",
        "outgoing": "requires",
        "style": "dotted",
    },
}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGACY_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGACY_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
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
def test_legacy_link_display_keys_are_deprecated_but_honoured(test_app):
    """The PlantUML-token link keys keep drawing exactly what they always drew.

    The deprecation is an alias, not a withdrawal: a project can move one link type at
    a time, and one that never moves keeps its diagrams.

    Graphviz matters as much as plantuml here, because it reaches these tokens through
    a whole translation layer of its own -- and that layer is what the entire
    deprecation story rests on.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "uses deprecated display key(s) style" in warnings
    assert "'line', 'part_line' and 'arrow'" in warnings

    debug = _debug_source(Path(app.outdir), "index.html")
    if app.config.needs_flow_engine == "plantuml":
        assert "-[dotted]->" in debug
    else:
        assert 'style="dotted"' in debug
        assert "arrowhead=vee" in debug


#: A link type that styles part links differently from ordinary ones.
PART_STYLING_CONF_PY = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "style": "node",
    },
]
needs_links = {
    "links": {
        "incoming": "is required by",
        "outgoing": "requires",
        "line": "solid",
        "color": "#00AA00",
        "part_line": "dotted",
        "part_color": "#777777",
    },
}
"""

PART_STYLING = """\
Part styling
============

.. spec:: A
   :id: AAAAA

   :np:`(subpart) a part of A`

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. spec:: C
   :id: CCCCC
   :links: AAAAA.subpart

.. needflow::
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), PART_STYLING_CONF_PY),
                (Path("index.rst"), PART_STYLING),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), PART_STYLING_CONF_PY),
                (Path("index.rst"), PART_STYLING),
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
def test_part_links_take_their_own_line_and_color(test_app):
    """A link to a need part can be drawn differently from an ordinary link.

    ``part_line`` and ``part_color`` each fall back to their ordinary counterpart when
    unset, so a link type says the difference once rather than describing both cases.
    Without ``part_color`` the deprecated ``style``/``style_part`` pair could express a
    distinction the neutral vocabulary could not, which left real configurations --
    including this project's own -- stuck on the deprecated spelling.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    debug = _debug_source(Path(app.outdir), "index.html")

    if app.config.needs_flow_engine == "plantuml":
        # the ordinary link: solid (no keyword) and green
        assert "-[#00AA00]->" in debug
        # the part link: dotted and grey
        assert "-[dotted,#777777]->" in debug
    else:
        assert 'style="solid"' in debug
        assert 'color="#00AA00"' in debug
        assert 'style="dotted"' in debug
        assert 'color="#777777"' in debug


#: A link type migrated halfway: a neutral ``line``, but its color still legacy.
HALF_MIGRATED_CONF_PY = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "style": "node",
    },
]
needs_links = {
    "links": {
        "incoming": "is required by",
        "outgoing": "requires",
        "style": "#00AA00",
        "line": "dashed",
    },
}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), HALF_MIGRATED_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), HALF_MIGRATED_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
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
def test_half_migrated_link_type_keeps_its_legacy_color(test_app):
    """Migrating one key of a link type must not silently drop another.

    The deprecated ``style`` is a compound of a color and a line keyword. Setting the
    neutral ``line`` supersedes that string, and dropping it wholesale took the color
    with it -- so a project migrating link types one at a time, which the changelog
    explicitly invites, lost its edge colors halfway through and was told nothing.
    """
    app = test_app
    app.build()

    debug = _debug_source(Path(app.outdir), "index.html")

    if app.config.needs_flow_engine == "plantuml":
        assert "-[dashed,#00AA00]->" in debug
    else:
        assert 'style="dashed"' in debug
        assert 'color="#00AA00"' in debug


#: The same half migration written the way a graphviz project writes it: the deprecated
#: ``style`` is a comma separated compound there, so the colour is one token of several.
HALF_MIGRATED_COMPOUND_CONF_PY = HALF_MIGRATED_CONF_PY.replace(
    '"style": "#00AA00",', '"style": "dotted,#FF0000",'
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), HALF_MIGRATED_COMPOUND_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), HALF_MIGRATED_COMPOUND_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
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
def test_legacy_style_folds_in_per_key_not_per_type(test_app):
    """Only the half of the legacy compound that was migrated is displaced.

    ``style`` may name a line *and* a colour at once. The neutral ``line`` supersedes
    the line keyword of that string and nothing else, so the colour token survives while
    ``dotted`` does not -- the fold is per key, not per link type.
    """
    app = test_app
    app.build()

    debug = _debug_source(Path(app.outdir), "index.html")

    if app.config.needs_flow_engine == "plantuml":
        assert "-[dashed,#FF0000]->" in debug
        assert "dotted" not in debug
    else:
        assert 'style="dashed"' in debug
        assert 'color="#FF0000"' in debug
        assert "dotted" not in debug


EXPLICIT_BLACK_CONF_PY = HALF_MIGRATED_CONF_PY.replace(
    '"style": "#00AA00",\n        "line": "dashed",', '"color": "#000000",'
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), EXPLICIT_BLACK_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
            ],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        }
    ],
    indirect=True,
)
def test_an_explicitly_black_link_color_is_drawn(test_app):
    """A link type may ask for black, and be given black.

    Treating black as "the same as unset" made the one color a user could not express
    the one the engine happens to default to -- which stops being harmless the moment
    an engine config sets an edge color of its own. Unset is the sentinel instead.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    assert 'color="#000000"' in _debug_source(Path(app.outdir), "index.html")


UNDRAWABLE_SHAPE_AND_ARROW_CONF_PY = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "shape": "diamond",
    },
]
needs_links = {
    "links": {
        "incoming": "is required by",
        "outgoing": "requires",
        "arrow": "cross",
    },
}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), UNDRAWABLE_SHAPE_AND_ARROW_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), UNDRAWABLE_SHAPE_AND_ARROW_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
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
def test_shapes_and_arrows_plantuml_cannot_draw_degrade_with_a_location(test_app):
    """A shape or arrow an engine has no form for degrades, once, and says where.

    Both are tier-2 gaps: the intent is named and this engine cannot honour it, so the
    project hears once and gets the nearest drawable form. Graphviz can draw both, so
    it must say nothing at all -- which is what makes these degradations and not errors.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).replace(
        str(app.srcdir) + os.path.sep, "<srcdir>/"
    )
    debug = _debug_source(Path(app.outdir), "index.html")

    if app.config.needs_flow_engine == "plantuml":
        assert warnings.count("has no 'diamond' shape") == 1
        assert warnings.count("has no crossed arrow head") == 1
        # the warning names the needflow it came from, not just the project
        assert re.search(r"<srcdir>/index\.rst:\d+: WARNING: the plantuml", warnings)
        # ...and the nearest drawable forms are used
        assert "rectangle " in debug
        assert "-> " in debug
    else:
        assert warnings.strip() == ""
        assert 'shape="diamond"' in debug
        assert "arrowhead=tee" in debug


#: A ``conf.py`` template whose single link type sets exactly one deprecated key.
_ONE_LEGACY_KEY_CONF_PY = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
needs_types = [
    {{
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "style": "node",
    }},
]
needs_links = {{
    "links": {{
        "incoming": "is required by",
        "outgoing": "requires",
        "{key}": "{value}",
    }},
}}
"""


@pytest.mark.parametrize(
    "key,value",
    [
        ("style", "dotted"),
        ("style_part", "dashed"),
        ("style_start", "<"),
        ("style_end", "->"),
    ],
)
def test_each_legacy_display_key_is_deprecated_on_its_own(
    make_app, tmp_path, plantuml_command, key, value
):
    """Every one of the four deprecated keys is reported, and only the ones used are.

    The warning is usage gated: it names exactly the keys the project wrote, so a
    project migrating one key at a time can see what is left to move -- and a project
    that has finished migrating hears nothing at all.
    """
    (tmp_path / "conf.py").write_text(
        _ONE_LEGACY_KEY_CONF_PY.format(key=key, value=value), "utf8"
    )
    (tmp_path / "index.rst").write_text(NEUTRAL_LINKS, "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    # the list of keys names exactly the one the project wrote, and nothing else
    named = re.findall(r"uses deprecated display key\(s\) ([^.]+)\.", warnings)
    assert named == [key]


NEUTRAL_ONLY_CONF_PY = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "shape": "rounded",
    },
]
needs_links = {
    "links": {
        "incoming": "is required by",
        "outgoing": "requires",
        "line": "thick",
        "part_line": "invisible",
        "arrow": "both",
        "color": "#112233",
        "part_color": "#445566",
    },
}
"""


def test_the_deprecation_is_silent_for_a_fully_migrated_project(
    make_app, tmp_path, plantuml_command
):
    """A project on the neutral keys alone hears nothing.

    This is the other half of the usage gate: the deprecation must be triggered by the
    *use* of a legacy key and by nothing else -- not by the neutral replacements being
    present, and not by the link type merely existing.
    """
    (tmp_path / "conf.py").write_text(NEUTRAL_ONLY_CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(NEUTRAL_LINKS, "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""


@pytest.mark.parametrize(
    "link,message,drawn",
    [
        (
            {"line": "wobbly", "style": "dotted"},
            "unknown 'line' 'wobbly' of link type 'links'",
            "-[dotted]->",
        ),
        (
            {"part_line": "wobbly", "style": "dotted"},
            "unknown 'part_line' 'wobbly' of link type 'links'",
            "-[dotted]->",
        ),
        (
            {"arrow": "boomerang", "style_end": "-*"},
            "unknown 'arrow' 'boomerang' of link type 'links'",
            "-*",
        ),
    ],
    ids=["line", "part_line", "arrow"],
)
def test_unusable_neutral_link_value_warns_and_falls_back(
    make_app, tmp_path, plantuml_command, link, message, drawn
):
    """An out-of-enum neutral value warns once and hands back to the legacy spelling.

    Every value here reaches a lookup table sooner or later, and reaching one unchecked
    is how a typo in one line of ``conf.py`` becomes a ``KeyError`` that ends the build.
    The documented fallback is the deprecated key, which is what the project had before
    it started migrating -- so a typo costs it the new value, never the diagram.
    """
    conf = LEGACY_CONF_PY.replace(
        '"style": "dotted",',
        "".join(f'"{key}": "{value}",\n        ' for key, value in link.items()),
    )
    (tmp_path / "conf.py").write_text(conf, "utf8")
    (tmp_path / "index.rst").write_text(NEUTRAL_LINKS, "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert message in warnings
    # said once for the project, not once per link or per diagram
    assert warnings.count(message) == 1
    assert drawn in _debug_source(Path(app.outdir), "index.html")


def test_unusable_neutral_type_shape_warns_and_falls_back(
    make_app, tmp_path, plantuml_command
):
    """An out-of-enum ``needs_types[].shape`` warns once and leaves ``style`` in charge."""
    conf = UNDRAWABLE_SHAPE_AND_ARROW_CONF_PY.replace(
        '"shape": "diamond",', '"shape": "trapezium",\n        "style": "card",'
    ).replace('"arrow": "cross",', "")
    (tmp_path / "conf.py").write_text(conf, "utf8")
    (tmp_path / "index.rst").write_text(NEUTRAL_LINKS, "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "unknown shape 'trapezium'" in warnings
    assert warnings.count("unknown shape 'trapezium'") == 1
    # the legacy `style` still draws the node
    assert "card " in _debug_source(Path(app.outdir), "index.html")


def test_unusable_neutral_values_are_reported_without_any_needflow(
    make_app, tmp_path, plantuml_command
):
    """The new keys are checked where they are read, as every sibling key already is.

    A project that misconfigures one of these and happens to have no needflow anywhere
    would otherwise never be told.
    """
    conf = NEUTRAL_CONF_PY.replace(
        '"shape": "cylinder",', '"shape": "trapezium",'
    ).replace('"line": "dashed",', '"line": "wobbly",')
    (tmp_path / "conf.py").write_text(conf, "utf8")
    (tmp_path / "index.rst").write_text(NO_NEEDFLOW, "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "unknown 'line' 'wobbly' of link type 'links'" in warnings
    assert "unknown shape 'trapezium'" in warnings


@pytest.mark.parametrize(
    "engine", ["plantuml", "graphviz"], ids=["plantuml", "graphviz"]
)
def test_neutral_values_ignore_case_and_padding(
    make_app, tmp_path, plantuml_command, engine
):
    """The new configuration values are matched the way the options already are.

    docutils' ``choice`` lowercases and strips before matching, so a value accepted in a
    directive must be accepted in ``conf.py`` too -- otherwise the asymmetry is internal
    to Sphinx-Needs, and it would make two implementations of this vocabulary disagree.
    """
    conf = (
        NEUTRAL_CONF_PY.replace('"shape": "cylinder",', '"shape": " Cylinder ",')
        .replace('"line": "dashed",', '"line": "  DASHED",')
        .replace('"arrow": "circle",', '"arrow": "Circle  ",')
    )
    (tmp_path / "conf.py").write_text(conf, "utf8")
    (tmp_path / "index.rst").write_text(NEUTRAL_LINKS, "utf8")
    confoverrides = {"plantuml": plantuml_command, "needs_flow_engine": engine}
    if engine == "graphviz":
        confoverrides["graphviz_output_format"] = "svg"
    app = make_app(srcdir=tmp_path, buildername="html", confoverrides=confoverrides)
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""
    debug = _debug_source(Path(app.outdir), "index.html")
    if engine == "plantuml":
        assert "database " in debug
        assert "[dashed,#00AA00]" in debug
    else:
        assert 'shape="cylinder"' in debug
        assert 'style="dashed"' in debug
        assert "arrowhead=odot" in debug


@pytest.mark.parametrize(
    "keyword,plantuml,graphviz",
    [
        ("database", "database ", 'shape="cylinder"'),
        ("card", "card ", 'shape="box", style="filled,rounded"'),
        ("usecase", "usecase ", 'shape="ellipse"'),
        ("artifact", "artifact ", 'shape="note"'),
    ],
)
@pytest.mark.parametrize(
    "engine", ["plantuml", "graphviz"], ids=["plantuml", "graphviz"]
)
def test_legacy_plantuml_keywords_are_accepted_as_shape_aliases(
    make_app, tmp_path, plantuml_command, keyword, plantuml, graphviz, engine
):
    """``shape`` accepts the values ``style`` has always held.

    That is what lets a project move a value from the old key to the new one unchanged
    and have it keep its meaning -- which is the whole point of the new key being an
    alias rather than a second, subtly different vocabulary.
    """
    conf = NEUTRAL_CONF_PY.replace('"shape": "cylinder",', f'"shape": "{keyword}",')
    (tmp_path / "conf.py").write_text(conf, "utf8")
    (tmp_path / "index.rst").write_text(NEUTRAL_LINKS, "utf8")
    confoverrides = {"plantuml": plantuml_command, "needs_flow_engine": engine}
    if engine == "graphviz":
        confoverrides["graphviz_output_format"] = "svg"
    app = make_app(srcdir=tmp_path, buildername="html", confoverrides=confoverrides)
    app.build()

    assert strip_colors(app._warning.getvalue()).strip() == ""
    debug = _debug_source(Path(app.outdir), "index.html")
    assert (plantuml if engine == "plantuml" else graphviz) in debug


#: Every member of the neutral arrow enum, with the plantuml arrow each must produce
#: when a line style is set as well -- which is where the tokens are concatenated with
#: the ``[...]`` between them, and so where a malformed pair actually shows up.
_ARROWS_WITH_A_LINE = [
    ("normal", "-[dashed,#00AA00]->"),
    ("none", "-[dashed,#00AA00]-"),
    ("open", "-[dashed,#00AA00]->"),
    ("circle", "-[dashed,#00AA00]-o"),
    ("cross", "-[dashed,#00AA00]->"),
    ("both", "<-[dashed,#00AA00]->"),
]


@pytest.mark.parametrize("arrow,expected", _ARROWS_WITH_A_LINE)
def test_every_arrow_renders_on_plantuml_beside_a_line(
    make_app, tmp_path, plantuml_command, arrow, expected
):
    """Each arrow of the enum must still be valid PlantUML once a line style joins it.

    The line style is written *between* the two arrow tokens (``-[dashed]->``), so a
    pair that only ever concatenates to a bare arrow renders on its own and becomes a
    syntax error the moment the link type also sets a line or a colour. PlantUML reports
    that as a render failure rather than as anything this vocabulary would notice, so the
    fence here is the whole build staying silent.
    """
    conf = NEUTRAL_CONF_PY.replace('"arrow": "circle",', f'"arrow": "{arrow}",')
    (tmp_path / "conf.py").write_text(conf, "utf8")
    (tmp_path / "index.rst").write_text(NEUTRAL_LINKS, "utf8")
    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command},
    )
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    # a malformed token pair reaches plantuml as a render failure, not as anything this
    # vocabulary would notice, so that is the assertion that matters here
    assert "error while running plantuml" not in warnings
    # `cross` is the one member plantuml has no head for, and says so (tier 2);
    # every other member must leave the build silent
    if arrow == "cross":
        assert warnings.count("has no crossed arrow head") == 1
    else:
        assert warnings == ""
    assert expected in _debug_source(Path(app.outdir), "index.html")


#: The mirror of the half migration above: the *colour* has moved to the neutral key
#: while the line keyword is still in the deprecated compound.
COLOR_MIGRATED_CONF_PY = HALF_MIGRATED_CONF_PY.replace(
    '"style": "#00AA00",\n        "line": "dashed",',
    '"style": "dotted,#FF0000",\n        "color": "#00AA00",',
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), COLOR_MIGRATED_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), COLOR_MIGRATED_CONF_PY),
                (Path("index.rst"), NEUTRAL_LINKS),
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
def test_a_migrated_color_supersedes_only_the_colour_token(test_app):
    """Migrating the colour out of ``style`` must not take the line keyword with it.

    This is the other direction of the same per-key fold: a neutral ``color`` supersedes
    the colour token of the deprecated compound -- the two cannot both be emitted -- and
    leaves everything else in that string doing exactly what it did. Dropping the string
    wholesale would silently turn a dotted edge solid.
    """
    app = test_app
    app.build()

    debug = _debug_source(Path(app.outdir), "index.html")

    if app.config.needs_flow_engine == "plantuml":
        assert "-[dotted,#00AA00]->" in debug
    else:
        assert 'style="dotted"' in debug
        assert 'color="#00AA00"' in debug
    # the superseded colour is emitted by neither engine
    assert "#FF0000" not in debug


#: A link type that states its line and colour once, for both edge kinds.
PART_FALLBACK_CONF_PY = PART_STYLING_CONF_PY.replace(
    '        "part_line": "dotted",\n        "part_color": "#777777",\n', ""
).replace('"line": "solid"', '"line": "dashed"')


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), PART_FALLBACK_CONF_PY),
                (Path("index.rst"), PART_STYLING),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), PART_FALLBACK_CONF_PY),
                (Path("index.rst"), PART_STYLING),
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
def test_part_line_and_part_color_fall_back_to_their_counterparts(test_app):
    """A link type that wants no distinction states its line and colour once.

    ``part_line`` and ``part_color`` are *overrides*, so an unset one takes ``line`` and
    ``color``. The two are symmetric on purpose: a rule that held for the colour and not
    for the line would have to be learnt rather than guessed, and it would leave a
    fully-migrated link type drawing its part edges from a deprecated default it never
    wrote.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    debug = _debug_source(Path(app.outdir), "index.html")

    if app.config.needs_flow_engine == "plantuml":
        # both edges: the ordinary line and the ordinary colour
        assert debug.count("-[dashed,#00AA00]->") == 2
        assert "dotted" not in debug
        assert "#777777" not in debug
    else:
        assert debug.count('style="dashed"') == 2
        assert debug.count('color="#00AA00"') == 2
        assert "dotted" not in debug
