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
    "engine,config_name,emitted",
    [
        ("plantuml", "lefttoright", "top to bottom direction"),
        ("graphviz", "lefttoright", 'rankdir="TB"'),
    ],
)
def test_explicit_direction_beats_the_engine_config(
    make_app, tmp_path, plantuml_command, engine, config_name, emitted
):
    """An explicit ``:direction:`` must win over the config blob written beside it.

    The blob is a preamble of defaults and the option a per-element value, which is the
    precedence both engines already give them -- but a *default* direction has to be
    restated to win, because emitting nothing would leave the blob's layout standing.
    The emitted source is asserted, so the test cannot pass on the warning alone.
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
