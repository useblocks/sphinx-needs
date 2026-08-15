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


LINK_LABELS = """\
Link labels
===========

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :debug:

.. needflow::
   :link_labels: outgoing
   :debug:

.. needflow::
   :link_labels: incoming
   :debug:

.. needflow::
   :link_labels: type
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), LINK_LABELS)],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), LINK_LABELS)],
            "confoverrides": {
                "needs_flow_engine": "graphviz",
                "graphviz_output_format": "svg",
            },
        },
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_link_labels_option(test_app):
    """``:link_labels:`` chooses what an edge is labelled with, or nothing at all.

    The tri-state replaces a flag that could only ever be turned on, so a diagram can
    now also opt out of a project default. All four values behave the same on both
    engines, which is the point of a portable option.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    outdir = Path(app.outdir)
    none = _debug_source(outdir, "index.html", 0)
    outgoing = _debug_source(outdir, "index.html", 1)
    incoming = _debug_source(outdir, "index.html", 2)
    by_type = _debug_source(outdir, "index.html", 3)

    assert "links outgoing" not in none
    assert "links incoming" not in none
    assert "links outgoing" in outgoing
    assert "links incoming" in incoming
    # the bare field name, for a diagram that wants the data model rather than prose
    assert "links incoming" not in by_type
    assert "links outgoing" not in by_type
    assert "links" in by_type


DEPRECATED_SHOW_LINK_NAMES = """\
Deprecated show_link_names
==========================

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :show_link_names:
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), DEPRECATED_SHOW_LINK_NAMES),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        }
    ],
    indirect=True,
)
def test_show_link_names_is_deprecated_but_honoured(test_app):
    """``:show_link_names:`` keeps working, and says once that it has a replacement.

    Deprecation upstream means an alias that is honoured indefinitely, so the only
    difference a reader sees is the warning; the diagram is exactly the one
    ``:link_labels: outgoing`` draws.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "'show_link_names' option is deprecated" in warnings
    assert "link_labels" in warnings

    assert "links outgoing" in _debug_source(Path(app.outdir), "index.html")


DEPRECATED_FLOW_SHOW_LINKS = """\
Deprecated needs_flow_show_links
================================

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :debug:

.. needflow::
   :link_labels: none
   :debug:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY),
                (Path("index.rst"), DEPRECATED_FLOW_SHOW_LINKS),
            ],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                "needs_flow_show_links": True,
            },
        }
    ],
    indirect=True,
)
def test_flow_show_links_is_deprecated_and_can_be_overridden(test_app):
    """``needs_flow_show_links`` is honoured, deprecated, and no longer inescapable.

    It used to be OR-ed with the option, so a project that turned labels on left no
    way of turning them off again for a single diagram. ``:link_labels: none`` is that
    way out, which is why the tri-state replaces the flag.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "'needs_flow_show_links' is deprecated" in warnings
    # a project wide deprecation is said once, not once per diagram
    assert warnings.count("'needs_flow_show_links' is deprecated") == 1

    outdir = Path(app.outdir)
    assert "links outgoing" in _debug_source(outdir, "index.html", 0)
    assert "links outgoing" not in _debug_source(outdir, "index.html", 1)


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
"""

LEGEND = """\
Legend
======

.. spec:: A
   :id: AAAAA

.. spec:: B
   :id: BBBBB
   :links: AAAAA

.. needflow::
   :legend: types

.. needflow::
   :legend: links

.. needflow::
   :legend: types,links

.. needflow::
   :legend:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), LEGEND),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), LEGEND),
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
def test_legend_option(test_app):
    """``:legend:`` draws a table beside the diagram, the same one on every engine.

    The legend is a document, not a picture: one implementation serves both engines
    (and any future one), it lists only what the diagram actually drew, and it can
    describe link types, which no in-diagram legend ever did. An explicitly empty
    value means "no legend", which is how a diagram opts out of a project default.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    tree = html_parser.parse(Path(app.outdir) / "index.html")
    legends = tree.xpath(_LEGEND_XPATH)

    # the fourth needflow asked for no legend at all
    assert len(legends) == 3

    types, links, both = (node.text_content() for node in legends)

    assert "Specification" in types
    # only the types that were drawn, not every configured type
    assert "Never Drawn" not in types
    assert "links outgoing" not in types

    assert "links outgoing" in links
    assert "Specification" not in links

    assert "Specification" in both
    assert "links outgoing" in both


LEGEND_UNDRAWN_LINKS = """\
Legend without edges
====================

.. spec:: A
   :id: AAAAA

.. needflow::
   :legend: links
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), LEGEND_UNDRAWN_LINKS),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        }
    ],
    indirect=True,
)
def test_legend_lists_only_drawn_link_types(test_app):
    """A link legend describes the edges that are there, not every configured link.

    A diagram with no edges has nothing to describe, so it gets no legend at all
    rather than an empty table of headings -- a legend listing link types the reader
    cannot see anywhere in the picture is worse than none.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    tree = html_parser.parse(Path(app.outdir) / "index.html")
    assert tree.xpath(_LEGEND_XPATH) == []


LEGEND_FROM_CONFIG = """\
Legend from config
==================

.. spec:: A
   :id: AAAAA

.. needflow::

.. needflow::
   :legend:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), LEGEND_FROM_CONFIG),
            ],
            "confoverrides": {
                "needs_flow_engine": "plantuml",
                "needs_flow_legend": "types",
            },
        }
    ],
    indirect=True,
)
def test_legend_config_is_consulted_only_when_unset(test_app):
    """``needs_flow_legend`` is a project default an explicitly empty option overrides.

    An empty value is not the same as an absent one, which is what makes opting out
    of a project default expressible at all.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).strip()
    assert warnings == ""

    tree = html_parser.parse(Path(app.outdir) / "index.html")
    legends = tree.xpath(_LEGEND_XPATH)
    assert len(legends) == 1
    assert "Specification" in legends[0].text_content()


DEPRECATED_SHOW_LEGEND = """\
Deprecated show_legend
======================

.. spec:: A
   :id: AAAAA

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
                (Path("index.rst"), DEPRECATED_SHOW_LEGEND),
            ],
            "confoverrides": {"needs_flow_engine": "plantuml"},
        },
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEGEND_CONF_PY),
                (Path("index.rst"), DEPRECATED_SHOW_LEGEND),
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
def test_show_legend_is_deprecated_and_keeps_drawing_in_the_diagram(test_app):
    """``:show_legend:`` still draws its old in-picture legend, and says so.

    Its rendering is deliberately left alone -- it differs per engine, which is the
    reason ``:legend:`` exists -- so nobody's diagram changes on upgrade.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "'show_legend' option is deprecated" in warnings
    assert "legend" in warnings

    debug = _debug_source(Path(app.outdir), "index.html")
    # the legacy legend is part of the diagram source, not a document table
    assert "Legend" in debug

    tree = html_parser.parse(Path(app.outdir) / "index.html")
    assert tree.xpath(_LEGEND_XPATH) == []


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
def test_invalid_flow_engine_warns_and_falls_back(test_app):
    """An unusable ``needs_flow_engine`` is a configuration mistake, not a crash.

    It used to trip a bare ``assert``, which ends a build with a traceback rather
    than a message naming the option and its allowed values.
    """
    app = test_app
    app.build()  # must not raise

    warnings = strip_colors(app._warning.getvalue())
    assert "Invalid 'needs_flow_engine' value 'mermaid'" in warnings
    assert "plantuml" in warnings
    # said once for the project, not once per diagram
    assert warnings.count("Invalid 'needs_flow_engine' value") == 1

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
        }
    ],
    indirect=True,
)
def test_legacy_link_display_keys_are_deprecated_but_honoured(test_app):
    """The PlantUML-token link keys keep drawing exactly what they always drew.

    The deprecation is an alias, not a withdrawal: a project can move one link type at
    a time, and one that never moves keeps its diagrams.
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue())
    assert "uses deprecated display key(s) style" in warnings
    assert "'line', 'part_line' and 'arrow'" in warnings

    assert "-[dotted]->" in _debug_source(Path(app.outdir), "index.html")


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
