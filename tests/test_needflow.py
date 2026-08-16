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


#: Selects the legend containers of a built page.
#: The class is matched as a whole token, so that the tables and color swatches
#: *inside* a legend -- whose classes also start with ``needflow_legend`` -- are not
#: mistaken for legends of their own.
_LEGEND_XPATH = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' needflow_legend ')]"
)


def _warnings_except(app, *allowed: str) -> list[str]:
    """Return a build's warnings, minus the ones a test knowingly provokes.

    A test that deliberately exercises a deprecated spelling still has to prove that
    nothing *else* went wrong, so the notice it expects is filtered out rather than
    the whole assertion being dropped.

    :param app: The built Sphinx application.
    :param allowed: Substrings identifying the warnings to ignore.
    :return: Every other warning line.
    """
    return [
        line
        for line in strip_colors(app._warning.getvalue()).strip().splitlines()
        if not any(text in line for text in allowed)
    ]


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


def _draws_internal_legend(source: str, engine: str) -> bool:
    """Whether an engine drew its own legend *inside* this diagram.

    Each engine opens its legend with a token of its own, so the token is matched
    rather than a bare substring that a need title could equally well contain. The
    ``:debug:`` block is line numbered, so ``legend`` is preceded by a digit rather
    than by a line start -- hence a lookbehind for a *letter*, which is what keeps
    ``endlegend`` from matching, rather than a word boundary, which a digit is not.

    :param source: The emitted diagram source, from :func:`_debug_source`.
    :param engine: The ``needs_flow_engine`` that emitted it.
    :return: True if the source contains that engine's in-diagram legend.
    """
    if engine == "plantuml":
        return re.search(r"(?<![A-Za-z])legend\n", source) is not None
    return "<B>Legend</B>" in source


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

    ``:border_color:`` is deprecated in favour of ``:styles:``, but is still honoured
    and so still has to normalise its value; the deprecation notice is therefore the
    only warning the build is allowed to produce.
    """
    app = test_app
    app.build()

    assert _warnings_except(app, "'border_color' option is deprecated") == []

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

    ``:highlight:`` is deprecated in favour of the built-in ``highlight`` style class,
    but is still honoured, so the deprecation notice is the only warning allowed.
    """
    app = test_app
    app.build()

    assert _warnings_except(app, "'highlight' option is deprecated") == []

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
    """An unknown engine config name must point at the values that could hold it.

    Each engine reads its own registry, and the plantuml message used to misspell it
    as ``need_flows_configs``, which does not exist. Both the new engine-keyed
    registry and the legacy one are named, since either could supply the name.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())

    if app.config.needs_flow_engine == "plantuml":
        assert (
            "config key 'nonexistent_cfg' not in "
            "'needs_flow_engine_config[plantuml]' or 'needs_flow_configs'" in warnings
        )
    else:
        assert (
            "config key 'nonexistent_cfg' not in "
            "'needs_flow_engine_config[graphviz]' or 'needs_graphviz_styles'"
            in warnings
        )
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


DIRECTIONS = """\
Directions
==========

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :debug:

.. needflow::
   :direction: right
   :debug:

.. needflow::
   :direction: up
   :debug:

.. needflow::
   :direction: LR
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), DIRECTIONS)],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), DIRECTIONS)],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_direction_option(test_app):
    """``:direction:`` expresses a layout intent that each engine spells its own way.

    The default is unchanged and emits nothing, so existing diagrams keep their bytes.
    PlantUML has no bottom-up primitive (verified: ``bottom to top direction`` is a
    syntax error), so ``up`` degrades to its axis mate ``down`` with a single warning,
    while graphviz renders it natively as ``rankdir=BT``.
    """
    app = test_app
    app.build()

    outdir = Path(app.outdir)
    default = _debug_source(outdir, "index.html", 0)
    right = _debug_source(outdir, "index.html", 1)
    up = _debug_source(outdir, "index.html", 2)
    alias = _debug_source(outdir, "index.html", 3)

    warnings = strip_colors(app._warning.getvalue())

    if app.config.needs_flow_engine == "plantuml":
        assert "direction" not in default
        assert "left to right direction" in right
        # degraded to its axis mate, which is how PlantUML already draws, so the
        # diagram needs no statement at all -- only the one warning tells the author
        assert "direction" not in up
        assert warnings.count("cannot draw 'up'") == 1
        assert "left to right direction" in alias
    else:
        assert "rankdir" not in default
        assert 'rankdir="LR"' in right
        assert 'rankdir="BT"' in up
        assert 'rankdir="LR"' in alias
        assert warnings.strip() == ""


DIRECTION_FROM_CONFIG = """\
Direction from an engine config
===============================

.. spec:: A
   :id: AAAAA

.. needflow::
   :config: lefttoright
   :debug:

.. needflow::
   :config: lefttoright
   :direction: down
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), DIRECTION_FROM_CONFIG),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), DIRECTION_FROM_CONFIG),
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
def test_explicit_direction_beats_config_direction(test_app):
    """An explicit ``:direction:`` overrides a direction carried by an engine config.

    The engine config blob is a preamble of defaults, and a neutral option is a
    per-element value, so the option is emitted last and wins. Because the two
    disagree here, the build says so rather than silently picking one.

    Both engines must behave the same way. The graphviz half is the one that was
    wrong: the shipped ``lefttoright`` config keys its ``rankdir`` under ``graph``,
    which the detection missed, so the disagreement went unnoticed and the blob won.
    """
    app = test_app
    app.build()

    outdir = Path(app.outdir)
    from_config = _debug_source(outdir, "index.html", 0)
    overridden = _debug_source(outdir, "index.html", 1)

    warnings = strip_colors(app._warning.getvalue())
    assert warnings.count("disagrees with the direction") == 1

    if app.config.needs_flow_engine == "plantuml":
        # the config alone still works, and is not restated
        assert from_config.count("left to right direction") == 1
        assert "top to bottom direction" not in from_config

        # the explicit option wins: its statement comes after the config blob
        assert overridden.index("left to right direction") < overridden.index(
            "top to bottom direction"
        )
    else:
        assert from_config.count('rankdir="LR"') == 1
        assert 'rankdir="TB"' not in from_config

        # the option's rankdir has to come after the `graph [...]` block, because a
        # graph attribute statement overrides an earlier top-level one
        assert overridden.index('rankdir="LR"') < overridden.index('rankdir="TB"')


DIRECTION_CONFIG_DEFAULT = """\
Project default direction
=========================

.. spec:: A
   :id: AAAAA

.. needflow::
   :debug:

.. needflow::
   :direction: down
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), DIRECTION_CONFIG_DEFAULT),
            ],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
                "needs_flow_direction": "right",
            },
        }
    ],
    indirect=True,
)
def test_direction_config_is_consulted_only_when_unset(test_app):
    """``needs_flow_direction`` is the project default, and an option overrides it.

    This is the ``max_items`` resolution rule: only an unset option consults the
    configuration, so a directive can always opt back out of a project default.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    outdir = Path(app.outdir)
    assert 'rankdir="LR"' in _debug_source(outdir, "index.html", 0)
    # the option opts back out to the default, which Graphviz already draws, so no
    # statement is needed -- the project default never reaches the diagram source
    assert "rankdir" not in _debug_source(outdir, "index.html", 1)


SHOW_LINK_NAMES_VALUES = """\
Link label values
=================

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :debug:

.. needflow::
   :show_link_names:
   :debug:

.. needflow::
   :show_link_names: outgoing
   :debug:

.. needflow::
   :show_link_names: incoming
   :debug:

.. needflow::
   :show_link_names: type
   :debug:

.. needflow::
   :show_link_names: none
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), SHOW_LINK_NAMES_VALUES),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), SHOW_LINK_NAMES_VALUES),
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
def test_show_link_names_takes_a_value(test_app):
    """``:show_link_names:`` chooses what an edge is labelled with, or nothing at all.

    The bare flag already meant exactly one of these values, so the option is widened
    rather than replaced: written without a value it still means ``outgoing``, and no
    existing document has to change. The other three are new, and the ``none`` value is
    what lets a diagram opt out of a project default -- which the flag could not
    express, because it could only ever turn labels on.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    outdir = Path(app.outdir)
    default = _debug_source(outdir, "index.html", 0)
    bare = _debug_source(outdir, "index.html", 1)
    outgoing = _debug_source(outdir, "index.html", 2)
    incoming = _debug_source(outdir, "index.html", 3)
    by_type = _debug_source(outdir, "index.html", 4)
    none = _debug_source(outdir, "index.html", 5)

    # the bare form is exactly what it has always been: the outgoing title
    assert bare == outgoing
    assert "links outgoing" in outgoing
    assert "links incoming" in incoming

    # unlabelled, whether by default or by asking
    for source in (default, none):
        assert "links outgoing" not in source
        assert "links incoming" not in source
    assert default == none

    # the bare field name, for a diagram that wants the data model rather than prose
    assert "links incoming" not in by_type
    assert "links outgoing" not in by_type
    assert "links" in by_type


FLOW_SHOW_LINKS_CONFIG = """\
Project default link labels
===========================

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :debug:

.. needflow::
   :show_link_names: none
   :debug:
"""


@pytest.mark.parametrize(
    "value,labelled",
    [
        (True, "links outgoing"),
        ("outgoing", "links outgoing"),
        ("incoming", "links incoming"),
        ("type", "links"),
        (False, None),
        ("none", None),
        # not a bool and not a string: this value was declared a bool for years, so
        # anything truthy drew labels and anything falsy did not
        (1, "links outgoing"),
        (0, None),
    ],
    ids=[
        "true",
        "outgoing",
        "incoming",
        "type",
        "false",
        "none",
        "truthy-non-bool",
        "falsy-non-bool",
    ],
)
@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
def test_flow_show_links_config_accepts_a_bool_or_a_value(
    make_app, tmp_path, plantuml_command, value, labelled, engine
):
    """``needs_flow_show_links`` takes the same values, and the booleans it always took.

    ``True`` has always meant "label with the outgoing title", so it keeps meaning
    exactly that and ``False`` means ``none``; the strings say the same things less
    ambiguously. A diagram can always have the last word, which it could not before:
    the flag and the option used to be OR-ed together, so a project that turned labels
    on left no way of turning them off again for one diagram.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(FLOW_SHOW_LINKS_CONFIG, "utf8")
    confoverrides = {
        "needs_flow_engine": engine,
        "plantuml": plantuml_command,
        "needs_flow_show_links": value,
    }
    if engine == "graphviz":
        confoverrides["graphviz_output_format"] = "svg"

    app = make_app(srcdir=tmp_path, buildername="html", confoverrides=confoverrides)
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    outdir = Path(app.outdir)
    from_config = _debug_source(outdir, "index.html", 0)
    overridden = _debug_source(outdir, "index.html", 1)

    if labelled is None:
        assert "links outgoing" not in from_config
        assert "links incoming" not in from_config
    else:
        assert labelled in from_config
        if labelled == "links":
            # `links` is a substring of both titles, so asserting its presence alone
            # cannot tell the bare field name apart from either of them
            assert "links outgoing" not in from_config
            assert "links incoming" not in from_config

    # whatever the project asked for, the diagram turned it off
    assert "links outgoing" not in overridden
    assert "links incoming" not in overridden


#: A ``conf.py`` with a second need type that no diagram below draws,
#: so that a "drawn types only" legend can be told apart from "all configured types".
LEGEND_CONF_PY = """\
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
    {
        "directive": "undrawn",
        "title": "Never Drawn",
        "prefix": "UN_",
        "color": "#CCCCCC",
        "style": "node",
    },
]
needs_flow_legends = {
    "beside": {"placement": "external"},
    "beside_links": {"parts": ["types", "links"], "placement": "external"},
    "inside": {"placement": "internal"},
    "inside_links": {"parts": ["links"], "placement": "internal"},
}
"""

LEGEND_KEYS = """\
Legend keys
===========

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :show_legend:
   :debug:

.. needflow::
   :show_legend: beside
   :debug:

.. needflow::
   :show_legend: beside_links
   :debug:

.. needflow::
   :show_legend: inside
   :debug:

.. needflow::
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), LEGEND_KEYS),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), LEGEND_KEYS),
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
def test_show_legend_takes_a_key(test_app):
    """``:show_legend:`` names a legend configuration, or nothing at all.

    The option takes a *key*, never an inline value, so the names a project chooses can
    never collide with a reserved word -- there is one namespace and no precedence rule
    to learn. Written bare it keeps drawing exactly the legend it always drew, which is
    each engine's own in-diagram one.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    outdir = Path(app.outdir)
    bare = _debug_source(outdir, "index.html", 0)
    external = _debug_source(outdir, "index.html", 1)
    external_links = _debug_source(outdir, "index.html", 2)
    internal = _debug_source(outdir, "index.html", 3)
    none = _debug_source(outdir, "index.html", 4)

    legends = html_parser.parse(outdir / "index.html").xpath(_LEGEND_XPATH)

    engine = app.config.needs_flow_engine
    assert _draws_internal_legend(bare, engine)

    # a key that only says where the legend goes still draws the same one, inside
    assert _draws_internal_legend(internal, engine)
    assert bare == internal

    # ...and asking for it beside the diagram takes it out of the picture entirely
    assert not _draws_internal_legend(external, engine)
    assert not _draws_internal_legend(external_links, engine)

    # a diagram that never asked has no legend anywhere
    assert not _draws_internal_legend(none, engine)

    # exactly the two external legends are rendered as document tables
    assert len(legends) == 2
    assert "Specification" in legends[0].text_content()
    assert "Never Drawn" not in legends[0].text_content()
    assert "links outgoing" not in legends[0].text_content()
    assert "links outgoing" in legends[1].text_content()


LEGEND_DEFAULT_KEY = """\
Project default legend key
==========================

.. spec:: A
   :id: AAAAA

.. needflow::
   :show_legend:
   :debug:

.. needflow::
   :show_legend: inside
   :debug:

.. needflow::
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), LEGEND_DEFAULT_KEY),
            ],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                "needs_flow_show_legend": "beside",
            },
        }
    ],
    indirect=True,
)
def test_show_legend_config_key_selects_which_not_whether(test_app):
    """``needs_flow_show_legend`` names which legend, never whether there is one.

    Presence stays per-directive, so a project default cannot turn legends on for
    diagrams that never asked -- which is also why the key namespace needs no off
    switch and so cannot collide with a legend name.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    outdir = Path(app.outdir)
    default_key = _debug_source(outdir, "index.html", 0)
    named = _debug_source(outdir, "index.html", 1)
    absent = _debug_source(outdir, "index.html", 2)

    engine = app.config.needs_flow_engine
    # the project default applies where the diagram named nothing (`beside`, so the
    # legend leaves the picture)...
    assert not _draws_internal_legend(default_key, engine)
    # ...loses to a diagram that named its own (`inside`)...
    assert _draws_internal_legend(named, engine)
    # ...and never reaches a diagram that did not ask at all
    assert not _draws_internal_legend(absent, engine)

    legends = html_parser.parse(outdir / "index.html").xpath(_LEGEND_XPATH)
    assert len(legends) == 1


UNKNOWN_LEGEND_KEY = """\
Unknown legend key
==================

.. spec:: A
   :id: AAAAA

.. needflow::
   :show_legend: nosuchkey
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), UNKNOWN_LEGEND_KEY),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        }
    ],
    indirect=True,
)
def test_unknown_legend_key_warns_and_draws_the_default(test_app):
    """Naming a legend that is not configured is an authoring mistake, not a build stop.

    It is reported against the directive that wrote it, with the keys that *are*
    available, and the diagram falls back rather than losing its legend -- a plainer
    diagram beats a failed build. This project sets no ``needs_flow_show_legend``, so
    the fallback lands on the last step of the chain, the engine's own legend;
    :func:`test_unknown_legend_option_key_falls_through_to_the_project_key` covers the step
    before it.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "legend key 'nosuchkey' is not defined in 'needs_flow_legends'" in warnings
    # the message names what the author could have written instead
    assert "available: beside, beside_links, inside, inside_links" in warnings
    # ...and it is reported against the directive that wrote it, not the project
    assert "index.rst:7" in warnings

    assert _draws_internal_legend(
        _debug_source(Path(app.outdir), "index.html"),
        app.config.needs_flow_engine,
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), UNKNOWN_LEGEND_KEY),
            ],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                # deliberately NOT the engine default: a project key that happened to
                # resolve to the same legend could not tell the two paths apart, which
                # is exactly the hole this test exists to close
                "needs_flow_show_legend": "beside",
            },
        }
    ],
    indirect=True,
)
def test_unknown_legend_option_key_falls_through_to_the_project_key(test_app):
    """An unusable option value is *treated as unset*, so the project default applies.

    This is the same rule the rest of the vocabulary already follows -- an unusable
    ``needs_flow_show_links`` string warns and behaves as though it had not been
    written -- and it is what makes the resolution a chain rather than a switch: option,
    then configuration, then the engine's own legend. A directive naming a legend that
    does not exist must not silently cost the project the legend it did configure.

    ``beside`` is external where the engine default is internal, so the two outcomes are
    distinguishable in the rendering rather than only in principle.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    # the mistake is still reported, against the directive that wrote it
    assert "legend key 'nosuchkey' is not defined in 'needs_flow_legends'" in warnings

    # ...and the project's own legend is what gets drawn, not the engine default
    debug = _debug_source(Path(app.outdir), "index.html")
    assert not _draws_internal_legend(debug, app.config.needs_flow_engine)

    legends = html_parser.parse(Path(app.outdir) / "index.html").xpath(_LEGEND_XPATH)
    assert len(legends) == 1
    assert "Specification" in legends[0].text_content()


UNKNOWN_PROJECT_LEGEND_KEY = """\
Unknown project legend key
==========================

.. spec:: A
   :id: AAAAA

.. needflow::
   :show_legend:
   :debug:

.. needflow::
   :show_legend:
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), UNKNOWN_PROJECT_LEGEND_KEY),
            ],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                "needs_flow_show_legend": "nosuchkey",
            },
        }
    ],
    indirect=True,
)
def test_unknown_project_legend_key_warns_once_and_draws_the_engine_default(test_app):
    """A misconfigured project default is the project's mistake, so it is said once.

    The chain ends at the engine's own legend, so every diagram still gets one. The
    warning is emitted once for the project rather than once per diagram: repeating a
    ``conf.py`` mistake at every needflow would bury the directive-level warnings that
    an author can actually act on.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    # said once for two diagrams, and it names the configuration key at fault rather
    # than reading like a mistake in the directive that happened to trigger it
    assert warnings.count("'needs_flow_show_legend'") == 1
    assert (
        "legend key 'nosuchkey' of 'needs_flow_show_legend' is not defined in "
        "'needs_flow_legends' (available: beside, beside_links, inside, inside_links)"
    ) in warnings

    # both diagrams still get a legend, the engine's own
    for index in (0, 1):
        assert _draws_internal_legend(
            _debug_source(Path(app.outdir), "index.html", index),
            app.config.needs_flow_engine,
        )


LEGEND_INTERNAL_WITH_LINKS = """\
Internal placement that cannot be honoured
==========================================

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :show_legend: inside_links
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), LEGEND_INTERNAL_WITH_LINKS),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), LEGEND_INTERNAL_WITH_LINKS),
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
def test_internal_placement_degrades_silently(test_app):
    """Placement is a preference, and failing to honour it is silent (tier 1).

    Neither in-diagram legend can describe link types, so a legend that asks for them
    is drawn beside the diagram instead. An external legend carries identical
    information and differs only in where it sits, which makes this a decorative
    nearest-form substitution rather than a capability gap worth a warning -- and a
    warning here would be unactionable on a configuration shared with a tool that can
    never satisfy it.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    debug = _debug_source(Path(app.outdir), "index.html")
    assert not _draws_internal_legend(debug, app.config.needs_flow_engine)

    legends = html_parser.parse(Path(app.outdir) / "index.html").xpath(_LEGEND_XPATH)
    assert len(legends) == 1
    assert "links outgoing" in legends[0].text_content()


BAD_LEGEND_CONFIG = """\
Bad legend config
=================

.. spec:: A
   :id: AAAAA

.. needflow::
   :show_legend: broken
   :debug:
"""


@pytest.mark.parametrize(
    "legends,message",
    [
        ('"not a mapping"', "'needs_flow_legends' must be a mapping of names"),
        (
            '{"broken": "not a mapping"}',
            "legend 'broken' in 'needs_flow_legends' must be a mapping",
        ),
        (
            '{"broken": {"nosuch": 1}}',
            "unknown key(s) ['nosuch'] of legend 'broken'",
        ),
        (
            '{"broken": {"parts": ["sections"]}}',
            "unknown legend section 'sections' of legend 'broken'",
        ),
        # a scalar is the shape a `parts` mistake actually takes -- an int is not
        # iterable at all, and a bare string iterates character by character, which
        # used to warn about five single letters and then draw a different legend
        (
            '{"broken": {"parts": 5}}',
            "'parts' of legend 'broken' must be a list, e.g. parts = [\"types\"]",
        ),
        (
            '{"broken": {"parts": "links"}}',
            "'parts' of legend 'broken' must be a list, e.g. parts = [\"types\"]",
        ),
        (
            '{"broken": {"parts": "both"}}',
            "'parts' of legend 'broken' must be a list, e.g. parts = [\"types\"]",
        ),
        (
            '{"broken": {"placement": "sideways"}}',
            "unknown placement 'sideways' of legend 'broken'",
        ),
    ],
    ids=[
        "not-a-mapping",
        "legend-not-a-mapping",
        "unknown-key",
        "unknown-section",
        "parts-not-a-list-int",
        "parts-not-a-list-str",
        "parts-not-a-list-both",
        "unknown-placement",
    ],
)
def test_unusable_legend_config_warns_and_draws_anyway(
    make_app, tmp_path, plantuml_command, legends, message
):
    """Every way of misdescribing a legend warns and leaves the diagram drawable.

    A legend is decoration: getting it wrong must not cost the reader the picture. Each
    rejection path is exercised -- the container, each entry, the key names, and each
    key's own value grammar -- because a closed vocabulary only helps if a value outside
    it is reported rather than silently dropped.

    The value is written into ``conf.py`` rather than passed as an override, because
    Sphinx refuses to override a dictionary setting with a value of another type -- and
    a hand-written ``conf.py`` is exactly where these mistakes are made.
    """
    (tmp_path / "conf.py").write_text(
        CONF_PY + f"\nneeds_flow_legends = {legends}\n", "utf8"
    )
    (tmp_path / "index.rst").write_text(BAD_LEGEND_CONFIG, "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "needs_flow_engine": "plantuml",
            "plantuml": plantuml_command,
        },
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert message in warnings

    # a `conf.py` mistake is reported against the project, not against whichever
    # directive happened to ask for the legend first -- the value is not written in
    # `index.rst` and an author sent there finds nothing to fix
    reported = [line for line in warnings.splitlines() if message in line]
    assert reported and not any("index.rst" in line for line in reported), reported

    # the legend is unusable, but the need is still drawn
    assert "AAAAA" in _debug_source(Path(app.outdir), "index.html")


@pytest.mark.parametrize(
    "name",
    ['""', '"   "', '"  padded  "'],
    ids=["empty", "blank", "padded"],
)
def test_unreachable_legend_key_is_reported_and_dropped(
    make_app, tmp_path, plantuml_command, name
):
    """A legend name no ``:show_legend:`` could ever select is reported, and dropped.

    Selectors are stripped before lookup and an empty one means "no name given", so a
    configured name that is empty, blank, or carries outside whitespace can never be
    matched however it is written. Keeping it would leave the author a legend that
    silently never appears, and would pad the "available:" list of an unknown-key
    warning with names that cannot be typed.
    """
    (tmp_path / "conf.py").write_text(
        CONF_PY + f"\nneeds_flow_legends = {{{name}: {{'placement': 'external'}}}}\n",
        "utf8",
    )
    (tmp_path / "index.rst").write_text(UNKNOWN_LEGEND_KEY, "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "needs_flow_engine": "plantuml",
            "plantuml": plantuml_command,
        },
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "in 'needs_flow_legends' can never be selected" in warnings

    # dropped, so it is not offered as an alternative to the unknown key either
    assert "available: none are defined" in warnings


#: Style classes exercising every property of the closed set.
FLOW_STYLES = {
    "danger": {
        "fill": "#FFDDDD",
        "border": "AA0000",
        "border_width": 3,
        "border_style": "dashed",
        "text_color": "#330000",
    },
    "shaped": {"shape": "hexagon"},
    "later": {"border": "00FF00"},
}

STYLES = """\
Styles
======

.. spec:: A
   :id: AAAAA
   :status: open

.. spec:: B
   :id: BBBBB

.. needflow::
   :styles: [status == 'open']:danger
   :debug:

.. needflow::
   :styles: shaped
   :debug:

.. needflow::
   :styles: danger, later
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), STYLES)],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                "needs_flow_styles": FLOW_STYLES,
            },
        },
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), STYLES)],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
                "needs_flow_styles": FLOW_STYLES,
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_styles_option(test_app):
    """``:styles:`` names configured classes and says which needs they apply to.

    The predicate half is the variant syntax the project already uses, so no third
    mini language is introduced, and the value half is a class name rather than
    inline properties, so a rule means the same thing on every engine. Declarations
    cascade like CSS ones: later wins, per property.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    outdir = Path(app.outdir)
    filtered = _debug_source(outdir, "index.html", 0)
    shaped = _debug_source(outdir, "index.html", 1)
    cascaded = _debug_source(outdir, "index.html", 2)

    if app.config.needs_flow_engine == "plantuml":
        # only the need the filter matched is styled
        assert filtered.count("line:AA0000") == 1
        assert filtered.count("FFDDDD") == 1
        assert "line.dashed" in filtered
        # a wide border has no plantuml counterpart, so it degrades to a bold line
        assert "line.bold" in filtered
        assert "text:330000" in filtered
        assert "hexagon " in shaped
        # the later rule wins on the property it sets, and only on that one
        assert "line:00FF00" in cascaded
        assert "line:AA0000" not in cascaded
        assert "FFDDDD" in cascaded
    else:
        assert filtered.count('color="#AA0000"') == 1
        assert filtered.count('fillcolor="#FFDDDD"') == 1
        assert "dashed" in filtered
        assert "penwidth=3" in filtered
        assert 'fontcolor="#330000"' in filtered
        assert 'shape="hexagon"' in shaped
        assert 'color="#00FF00"' in cascaded
        assert 'color="#AA0000"' not in cascaded
        assert 'fillcolor="#FFDDDD"' in cascaded


UNKNOWN_STYLE_CLASS = """\
Unknown style class
===================

.. spec:: A
   :id: AAAAA

.. needflow::
   :styles: nonexistent
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), UNKNOWN_STYLE_CLASS),
            ],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                "needs_flow_styles": FLOW_STYLES,
            },
        }
    ],
    indirect=True,
)
def test_unknown_style_class_warns_and_draws_anyway(test_app):
    """Naming a class that is not configured is an authoring mistake, not a build stop.

    A missing style is reported against the directive that asked for it, and the
    diagram is drawn without it -- a plainer diagram beats a failed build.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "style class 'nonexistent' is not defined in 'needs_flow_styles'" in warnings
    assert "AAAAA" in _get_svg(
        app.config, Path(app.outdir), "index.html", "needflow-index-0"
    )


NON_DICT_STYLES = """\
Malformed style config
======================

.. spec:: A
   :id: AAAAA

.. needflow::
   :styles: broken
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), NON_DICT_STYLES),
            ],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                "needs_flow_styles": {"broken": "not a mapping"},
            },
        }
    ],
    indirect=True,
)
def test_malformed_style_class_warns_and_draws_anyway(test_app):
    """A style class that is not a mapping of properties must not stop the build."""
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "must be a mapping of properties" in warnings
    assert "AAAAA" in _get_svg(
        app.config, Path(app.outdir), "index.html", "needflow-index-0"
    )


HIGHLIGHT_SUGAR = """\
Highlight as a style class
==========================

.. spec:: A
   :id: AAAAA
   :status: open

.. needflow::
   :highlight: status == 'open'
   :debug:

.. needflow::
   :styles: [status == 'open']:highlight
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), HIGHLIGHT_SUGAR)],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), HIGHLIGHT_SUGAR)],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_highlight_is_sugar_for_the_builtin_style_class(test_app):
    """``:highlight:`` is the built-in ``highlight`` class, and draws exactly as before.

    The class is rendered in each engine's legacy red-outline form rather than through
    the property machinery, so a project migrating from the option to the class gets a
    byte-identical diagram.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "'highlight' option is deprecated" in warnings

    outdir = Path(app.outdir)
    legacy = _debug_source(outdir, "index.html", 0)
    as_class = _debug_source(outdir, "index.html", 1)

    assert legacy == as_class
    if app.config.needs_flow_engine == "plantuml":
        assert "line:FF0000" in legacy
    else:
        assert "color=red" in legacy


ENGINE_CONFIG = """\
Engine config
=============

.. spec:: A
   :id: AAAAA

.. needflow::
   :engine_config: corporate
   :debug:

.. needflow::
   :config: corporate
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), ENGINE_CONFIG)],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                "needs_flow_engine_config": {
                    "plantuml": {"corporate": "skinparam backgroundColor #EEEEEE"}
                },
            },
        }
    ],
    indirect=True,
)
def test_engine_config_hatch(test_app):
    """``:engine_config:`` is the one discouraged way through to engine specific syntax.

    Documents stay portable, projects may choose not to be: the blob lives in the
    configuration under the engine it belongs to, and the document only names it.
    ``:config:`` is the deprecated spelling of the same selector, so both draw the
    same diagram.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "'config' option is deprecated" in warnings
    assert "engine_config" in warnings
    assert _warnings_except(app, "'config' option is deprecated") == []

    outdir = Path(app.outdir)
    assert "skinparam backgroundColor #EEEEEE" in _debug_source(outdir, "index.html", 0)
    assert _debug_source(outdir, "index.html", 0) == _debug_source(
        outdir, "index.html", 1
    )


LEGACY_ENGINE_CONFIG = """\
Legacy engine config registry
=============================

.. spec:: A
   :id: AAAAA

.. needflow::
   :engine_config: legacy
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), LEGACY_ENGINE_CONFIG),
            ],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                "needs_flow_configs": {"legacy": "skinparam shadowing false"},
            },
        }
    ],
    indirect=True,
)
def test_engine_config_still_reads_the_legacy_registry(test_app):
    """The new selector reads the old registries, so no project has to move its blobs.

    The registries are a rename, not a redesign: the same values mean the same thing
    under either name, which is what makes the migration free.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    assert "skinparam shadowing false" in _debug_source(Path(app.outdir), "index.html")


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
                "needs_graphviz_styles": {"default": {"node": "not-a-mapping"}},
            },
        }
    ],
    indirect=True,
)
def test_malformed_graphviz_style_warns_instead_of_crashing(test_app):
    """A graphviz style entry that is not a mapping must not fail the whole build.

    The value used to travel unchecked from the configuration into the emitter, where
    ``'str' object has no attribute 'items'`` aborted the build with a traceback
    instead of a message. It is now rejected where it is read, and the diagram is
    drawn without it.
    """
    app = test_app
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "must be a mapping of attributes" in warnings

    assert "AAAAA" in _get_svg(
        app.config, Path(app.outdir), "index.html", "needflow-index-0"
    )


INVALID_ENGINE = """\
Invalid engine
==============

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
                (Path("index.rst"), INVALID_ENGINE),
            ],
            "confoverrides": {"needs_flow_engine": "mermaid"},
        }
    ],
    indirect=True,
)
def test_reserved_flow_engine_config_falls_back(test_app):
    """``needs_flow_engine = "mermaid"`` is accepted project-wide and degrades.

    The configuration counterpart of the ``:engine:`` option: the name is reserved for
    ubCode rather than rejected, so a shared configuration can name it without the
    Sphinx-Needs build losing every diagram. It used to trip a bare ``assert``, which
    ends a build with a traceback rather than a message.
    """
    app = test_app
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "the 'mermaid' engine is not available in Sphinx-Needs" in warnings
    assert "'plantuml' instead" in warnings
    # said once for the project, not once per diagram
    assert warnings.count("engine is not available") == 1
    # ...and it is not reported as an invalid value, because it is a valid one
    assert "Invalid 'needs_flow_engine'" not in warnings

    # the fallback engine still drew a diagram, rather than the build ending
    assert "needflow-index-0" in Path(app.outdir, "index.html").read_text()


PLANTUML_CLASS_AND_DEBUG = """\
Class and debug on plantuml
===========================

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
                (Path("index.rst"), PLANTUML_CLASS_AND_DEBUG),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), PLANTUML_CLASS_AND_DEBUG),
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
def test_class_and_debug_behave_the_same_on_both_engines(test_app):
    """``:class:`` and ``:debug:`` must mean the same thing whichever engine draws.

    ``:class:`` was collected by the directive and then dropped by the plantuml
    engine, so the same option styled a graphviz diagram and did nothing to a plantuml
    one. ``:debug:`` produced raw HTML on plantuml and a highlighted literal block on
    graphviz; both now produce a literal block.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    page = Path(app.outdir, "index.html").read_text()
    assert "my-flow-class" in page

    tree = html_parser.parse(Path(app.outdir) / "index.html")
    # a literal block, i.e. inside a highlight container, on either engine
    blocks = tree.xpath(
        "//div[contains(concat(' ', normalize-space(@class), ' '), ' highlight ')]//pre"
    )
    assert len(blocks) == 1
    assert "AAAAA" in blocks[0].text_content()


DEPRECATED_SCALE = """\
Deprecated scale
================

.. spec:: A
   :id: AAAAA

.. needflow::
   :scale: 50
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), DEPRECATED_SCALE),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        }
    ],
    indirect=True,
)
def test_scale_is_deprecated_without_a_like_for_like_replacement(test_app):
    """``:scale:`` sizes a raster image, which graphviz has always silently ignored.

    Deprecating it is honesty rather than loss: the option never did the same thing
    on both engines, and ``:width:``/``:height:`` are what a portable document should
    say instead.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "'scale' option is deprecated" in warnings
    assert ":width:" in warnings


DEAD_FLOW_LINK_TYPES = """\
Dead needs_flow_link_types
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
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), DEAD_FLOW_LINK_TYPES),
            ],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                "needs_flow_link_types": ["blocks"],
            },
        }
    ],
    indirect=True,
)
def test_flow_link_types_is_deprecated_as_dead(test_app):
    """``needs_flow_link_types`` is deprecated because it has never had any effect.

    The directive always defaults its ``:link_types:`` option to every link field, so
    the configuration is unreachable. Making it work now would silently narrow every
    existing diagram, so it is documented as dead instead -- and the edge below is
    still drawn, proving the value really is ignored.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert '"needs_flow_link_types" is deprecated and has no effect' in warnings

    # the `links` edge is drawn even though the config named only `blocks`
    assert "BBBBB --> AAAAA" in _debug_source(Path(app.outdir), "index.html")


#: A ``conf.py`` whose link type and need type use the neutral vocabulary.
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
        assert 'arrowhead="odot"' in debug or "arrowhead=odot" in debug
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


GRAPH_KEYED_DIRECTION = """\
Graph keyed rankdir
===================

.. spec:: A
   :id: AAAAA

.. needflow::
   :engine_config: sideways
   :debug:

.. needflow::
   :engine_config: sideways
   :direction: down
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), GRAPH_KEYED_DIRECTION),
            ],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
                "needs_flow_engine_config": {
                    "graphviz": {
                        "sideways": {"graph": {"rankdir": "LR"}},
                    }
                },
            },
        }
    ],
    indirect=True,
)
def test_graph_keyed_rankdir_is_detected_and_overridable(test_app):
    """A ``rankdir`` inside a ``graph [...]`` block still loses to ``:direction:``.

    ``rankdir`` is a graph attribute, and the shape the documentation teaches -- and the
    shipped ``lefttoright`` config uses -- keys it under ``graph`` rather than at the top
    level. Detecting only the top level form meant the engine config silently won on
    graphviz, which is the one thing the published collision rule says cannot happen.
    """
    app = test_app
    app.build()

    outdir = Path(app.outdir)
    from_config = _debug_source(outdir, "index.html", 0)
    overridden = _debug_source(outdir, "index.html", 1)

    # the config alone is honoured and not restated
    assert from_config.count('rankdir="LR"') == 1

    # the option wins, and says so, because a later statement overrides the block
    assert overridden.index('rankdir="LR"') < overridden.index('rankdir="TB"')

    warnings = strip_colors(app._warning.getvalue())
    assert warnings.count("disagrees with the direction") == 1


BAD_CONFIG_VALUE = """\
Bad config value
================

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :debug:
"""


@pytest.mark.parametrize(
    "override,message",
    [
        ({"needs_flow_direction": "sideways"}, "Invalid 'needs_flow_direction' value"),
        ({"needs_flow_show_links": "bogus"}, "Invalid 'needs_flow_show_links' value"),
    ],
    ids=["direction", "show_links"],
)
@pytest.mark.parametrize("engine", ["plantuml", "graphviz"])
def test_out_of_enum_config_values_warn_and_fall_back(
    make_app, tmp_path, plantuml_command, override, message, engine
):
    """An out-of-enum configuration value must warn, never end the build.

    ``needs_flow_direction`` used to be read straight into a lookup table, so a typo
    reached it as a ``KeyError`` and aborted the build with a traceback -- the exact
    failure mode this slice removed for ``needs_flow_engine``. Every enumerated
    configuration value is now validated the same way: one ``needs.config`` warning
    naming the allowed values, then the documented default.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(BAD_CONFIG_VALUE, "utf8")
    confoverrides = {
        "needs_flow_engine": engine,
        "plantuml": plantuml_command,
        **override,
    }
    if engine == "graphviz":
        confoverrides["graphviz_output_format"] = "svg"

    app = make_app(srcdir=tmp_path, buildername="html", confoverrides=confoverrides)
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert message in warnings
    # said once for the project, not once per diagram
    assert warnings.count(message) == 1

    # the diagram is still drawn, with the default the warning names
    assert "AAAAA" in _debug_source(Path(app.outdir), "index.html")


RESERVED_ENGINE = """\
Reserved engine
===============

.. spec:: A
   :id: AAAAA

.. needflow::
   :engine: mermaid
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), RESERVED_ENGINE),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        }
    ],
    indirect=True,
)
def test_reserved_mermaid_engine_option_degrades(test_app):
    """``:engine: mermaid`` is accepted and degrades, rather than dropping the directive.

    ubCode draws needflows with mermaid, and a document naming it must not become
    unportable the moment it is rendered here -- which is what a hard docutils error
    made it, because the directive was discarded entirely.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "'mermaid' engine is not available" in warnings
    assert warnings.count("'mermaid' engine is not available") == 1

    # the diagram is drawn by the fallback engine rather than lost
    assert "AAAAA" in _debug_source(Path(app.outdir), "index.html")


NO_NEEDFLOW = """\
No needflow here
================

.. spec:: A
   :id: AAAAA
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), NO_NEEDFLOW)],
            "confoverrides": {"needs_flow_engine": "nonsuch"},
        }
    ],
    indirect=True,
)
def test_invalid_flow_engine_is_reported_without_any_needflow(test_app):
    """An unusable ``needs_flow_engine`` is a configuration fault, reported at load time.

    Checking it as a diagram is drawn means a project that misconfigures it and happens
    to have no needflow is never told; the check belongs where the configuration is
    read, so it fires exactly once whether or not anything uses it.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "Invalid 'needs_flow_engine' value 'nonsuch'" in warnings
    assert warnings.count("Invalid 'needs_flow_engine' value") == 1


@pytest.mark.parametrize(
    "override,message",
    [
        ({"needs_flow_direction": "sideways"}, "Invalid 'needs_flow_direction' value"),
        ({"needs_flow_show_links": "bogus"}, "Invalid 'needs_flow_show_links' value"),
        (
            {"needs_flow_legends": {"broken": {"placement": "sideways"}}},
            "unknown placement 'sideways' of legend 'broken'",
        ),
        (
            {"needs_flow_legends": {"broken": {"parts": "links"}}},
            "'parts' of legend 'broken' must be a list",
        ),
        (
            {"needs_flow_show_legend": "alsobad"},
            "legend key 'alsobad' of 'needs_flow_show_legend' is not defined",
        ),
    ],
    ids=[
        "direction",
        "show_links",
        "legends-placement",
        "legends-parts",
        "show_legend",
    ],
)
def test_bad_flow_config_is_reported_without_any_needflow(
    make_app, tmp_path, plantuml_command, override, message
):
    """Every enumerated needflow value is checked where the configuration is read.

    ``needs_flow_engine`` already was, and the rest were only checked as a diagram was
    drawn -- so a project that misconfigured one of them and happened to have no
    needflow anywhere heard nothing at all. They are now consistent, and still warn
    exactly once for a project that does draw diagrams.

    The two legend keys belong here for the same reason as the rest, and their absence
    was a regression against the release that had ``needs_flow_legend``: that one was a
    plain string checked at read time, so the project below used to be told.
    """
    (tmp_path / "conf.py").write_text(CONF_PY, "utf8")
    (tmp_path / "index.rst").write_text(NO_NEEDFLOW, "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={"plantuml": plantuml_command, **override},
    )
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert message in warnings
    assert warnings.count(message) == 1


NESTED_FILL = """\
Nested need fill
================

.. spec:: Parent
   :id: PARENT

   .. spec:: Child
      :id: CHILD

.. needflow::
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), NESTED_FILL)],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        }
    ],
    indirect=True,
)
def test_subgraph_style_stays_unquoted(test_app):
    """A clustered need keeps writing a bare ``style=filled``.

    Graphviz treats ``filled`` and ``"filled"`` alike, but the generated image file is
    named after a hash of this source, so quoting it renames every image of every
    project that nests needs on its first rebuild. The plain node path has always
    quoted and the subgraph path has always not; unifying the two emitters must not
    quietly change either.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    debug = _debug_source(Path(app.outdir), "index.html")

    # the parent is a subgraph (bare), the child a plain node (quoted)
    assert "  style=filled;" in debug
    assert 'style="filled"' in debug


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


UNKNOWN_CLASS_FIRST = """\
First document
==============

.. spec:: A
   :id: AAAAA

.. needflow::
   :styles: nosuchclass
"""

UNKNOWN_CLASS_SECOND = """\
Second document
===============

.. spec:: B
   :id: BBBBB

.. needflow::
   :styles: nosuchclass
"""

UNKNOWN_CLASS_INDEX = """\
Index
=====

.. toctree::

   first
   second
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), UNKNOWN_CLASS_INDEX),
                (Path("first.rst"), UNKNOWN_CLASS_FIRST),
                (Path("second.rst"), UNKNOWN_CLASS_SECOND),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        }
    ],
    indirect=True,
)
def test_unknown_style_class_warns_once_per_directive(test_app):
    """Naming a class that is not configured is reported wherever it happens.

    It is an authoring mistake, which the degradation policy puts in the tier that
    warns per directive -- a project-wide once-filter hides every occurrence after the
    first, so the same typo in twenty documents produced one warning pointing at one of
    them.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert warnings.count("style class 'nosuchclass' is not defined") == 2
    assert "first.rst" in warnings
    assert "second.rst" in warnings


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


BAD_STYLE_CONFIG = """\
Bad style config
================

.. spec:: A
   :id: AAAAA

.. needflow::
   :styles: broken
   :debug:
"""


@pytest.mark.parametrize(
    "styles,message",
    [
        ('"not a mapping"', "'needs_flow_styles' must be a mapping of class names"),
        ('{"broken": "not a mapping"}', "must be a mapping of properties"),
        (
            '{"broken": {"nosuch": 1}}',
            "unknown property 'nosuch' of style class 'broken'",
        ),
        (
            '{"broken": {"border_width": "wide"}}',
            "'border_width' of style class 'broken' must be a number",
        ),
        (
            '{"broken": {"border_style": "wiggly"}}',
            "unknown 'border_style' 'wiggly' of style class 'broken'",
        ),
        ('{"broken": {"shape": "trapezoid"}}', "unknown shape 'trapezoid'"),
    ],
    ids=[
        "not-a-mapping",
        "class-not-a-mapping",
        "unknown-property",
        "bad-width",
        "bad-line",
        "bad-shape",
    ],
)
def test_unusable_style_config_warns_and_draws_anyway(
    make_app, tmp_path, plantuml_command, styles, message
):
    """Every way of misdescribing a style class warns and leaves the diagram drawable.

    The closed property set only helps if a value outside it is reported rather than
    silently dropped or fatally applied, so each rejection path is exercised: the
    container, each class, the property name, and each property's own value grammar.

    The value is written into ``conf.py`` rather than passed as an override, because
    Sphinx refuses to override a dictionary setting with a value of another type -- and
    a hand-written ``conf.py`` is exactly where these mistakes are made.
    """
    (tmp_path / "conf.py").write_text(
        CONF_PY + f"\nneeds_flow_styles = {styles}\n", "utf8"
    )
    (tmp_path / "index.rst").write_text(BAD_STYLE_CONFIG, "utf8")

    app = make_app(
        srcdir=tmp_path,
        buildername="html",
        confoverrides={
            "needs_flow_engine": "plantuml",
            "plantuml": plantuml_command,
        },
    )
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert message in warnings

    # the class is unusable, but the need is still drawn
    assert "AAAAA" in _debug_source(Path(app.outdir), "index.html")


BAD_DIRECTION_OPTION = """\
Bad direction option
====================

.. spec:: A
   :id: AAAAA

.. needflow::
   :direction: sideways
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), BAD_DIRECTION_OPTION),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        }
    ],
    indirect=True,
)
def test_unknown_direction_value_is_an_option_error(test_app):
    """An out-of-enum *option* value is reported by docutils as the option is parsed.

    That is the one tier where erroring is right: the author wrote something the
    vocabulary does not contain, in the document, where it can be corrected -- as
    opposed to a configuration value, which degrades so that one typo cannot stop a
    whole build.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert '"sideways" unknown' in warnings
    assert "down" in warnings and "up" in warnings


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
    "override,needle,in_diagram",
    [
        ({"needs_flow_show_links": "  Outgoing  "}, "links outgoing", True),
        ({"needs_flow_direction": "  RIGHT  "}, "left to right direction", True),
        ({"needs_flow_engine": "  GraphViz  "}, "digraph needflow", True),
    ],
    ids=["show_links", "direction", "engine"],
)
def test_enum_config_values_ignore_case_and_padding(
    make_app, tmp_path, plantuml_command, override, needle, in_diagram
):
    """A configured enum value is matched the way the matching option value is.

    The directive options go through docutils' ``choice``, which lowercases and strips
    before matching, so ``:show_link_names: Outgoing`` has always been accepted. The
    configuration side matched exactly, so the same word in ``conf.py`` warned and fell
    back -- silently drawing something else. That asymmetry was internal to Sphinx-Needs
    and it also made the two implementations of this vocabulary disagree, since ubCode
    normalises both halves.
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
    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    # the diagram source is read from the `:debug:` block rather than the raw markup,
    # which the graphviz engine syntax highlights into per-token spans
    haystack = (
        _debug_source(Path(app.outdir), "index.html")
        if in_diagram
        else Path(app.outdir, "index.html").read_text()
    )
    assert needle in haystack


@pytest.mark.parametrize(
    "override,message",
    [
        ({"needs_flow_show_links": "  Outgoinggg  "}, "'needs_flow_show_links'"),
        ({"needs_flow_direction": "  sideways  "}, "'needs_flow_direction'"),
        ({"needs_flow_engine": "  crayon  "}, "'needs_flow_engine'"),
    ],
    ids=["show_links", "direction", "engine"],
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
    assert f"Invalid {message} value" in warnings
    # the author's own spelling is echoed, padding and all, so it can be found in conf.py
    assert repr(next(iter(override.values()))) in warnings
