"""Unit tests for the engine independent needflow graph model.

The model is what both needflow engines draw from, so the rules tested here -- which
needs the root walk reaches, which link types may be drawn, how a need is presented, and
which links become edges -- decide what *every* engine renders.  They are exercised
directly, without building a documentation project, so that a change in one of them is
reported as a rule that changed rather than as a diagram that moved.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import Mock

import pytest
from docutils import nodes

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsFlowType
from sphinx_needs.directives.needflow._model import (
    GraphNode,
    NodePresentation,
    build_node_tree,
    collect_edges,
    filter_by_tree,
    get_root_needs,
    resolve_color,
    resolve_link_types,
    resolve_presentation,
)
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.need_item import (
    NeedItem,
    NeedItemSourceDirective,
    NeedPartData,
    NeedsContent,
)
from sphinx_needs.needs_schema import FieldsSchema, LinkDisplayConfig, LinkSchema
from sphinx_needs.views import NeedsView

CORE_BASE: dict[str, Any] = {
    "id": "",
    "type": "story",
    "type_name": "User Story",
    "type_prefix": "US_",
    "type_color": "#BFD8D2",
    "type_style": "node",
    "status": None,
    "tags": [],
    "constraints": (),
    "title": "title",
    "collapse": False,
    "arch": {},
    "style": None,
    "layout": None,
    "hide": False,
    "external_css": "external_link",
    "has_dead_links": False,
    "has_forbidden_dead_links": False,
    "sections": (),
    "signature": None,
}


def need(
    id: str,
    *,
    links: list[str] | None = None,
    blocks: list[str] | None = None,
    parent: str | None = None,
    children: list[str] | None = None,
    incoming: list[str] | None = None,
    parts: tuple[str, ...] = (),
    docname: str | None = None,
    **core: Any,
) -> NeedItem:
    """Create a need item, with only the fields the graph model looks at.

    :param links: The ids the need links to.
    :param blocks: The ids the need blocks, a second link type.
    :param parent: The id of the need this one is nested in.
    :param children: The ids of the needs nested in this one.
    :param incoming: The ids of the needs linking to this one.
    :param parts: The ids of the parts of the need.
    :param docname: The document the need is defined in, if it matters.
    """
    return NeedItem(
        core={**CORE_BASE, "id": id, **core},
        content=NeedsContent(content="content", doctype=".rst"),
        extras={},
        links={
            "links": links or [],
            "blocks": blocks or [],
            "parent_needs": [parent] if parent else [],
        },
        backlinks={
            "links": incoming or [],
            "blocks": [],
            "parent_needs": children or [],
        },
        parts=tuple(NeedPartData(id=part, content=f"part {part}") for part in parts),
        source=(
            NeedItemSourceDirective(docname=docname, lineno=1, lineno_content=1)
            if docname is not None
            else None
        ),
    )


def view(*needs: NeedItem) -> NeedsView:
    """Create a needs view of the given needs."""
    return NeedsView._from_needs({n["id"]: n for n in needs})


def link_schema(name: str = "links", **display: Any) -> LinkSchema:
    """Create a link field schema with the given display configuration."""
    return LinkSchema(
        name=name,
        schema={"type": "array", "items": {"type": "string"}},
        display=LinkDisplayConfig(outgoing=name, incoming=f"{name} back", **display),
    )


def flow(**options: Any) -> NeedsFlowType:
    """Create the needflow options that the model reads."""
    return {  # type: ignore[typeddict-item]
        "target_id": "needflow-index-0",
        "link_types": [],
        "highlight": "",
        "border_color": None,
        "show_link_names": False,
        **options,
    }


# --- the root walk -------------------------------------------------------------------


def test_walk_returns_only_the_root_when_it_is_unconnected():
    needs = view(need("A"), need("B"))
    assert set(filter_by_tree(needs, "A", ["links"], "both", None)) == {"A"}


def test_walk_of_an_unknown_root_returns_nothing():
    """A root that is not a need cannot select anything, rather than everything."""
    needs = view(need("A"), need("B"))
    assert set(filter_by_tree(needs, "MISSING", ["links"], "both", None)) == set()


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        ("outgoing", {"B", "C"}),
        ("incoming", {"B", "A"}),
        ("both", {"A", "B", "C"}),
    ],
)
def test_walk_follows_the_given_direction(direction, expected):
    """``outgoing`` follows links, ``incoming`` follows back links, ``both`` follows both."""
    a = need("A", links=["B"])
    b = need("B", links=["C"], incoming=["A"])
    c = need("C", incoming=["B"])
    assert (
        set(filter_by_tree(view(a, b, c), "B", ["links"], direction, None)) == expected
    )


@pytest.mark.parametrize(
    ("depth", "expected"),
    [(0, {"A"}), (1, {"A", "B"}), (2, {"A", "B", "C"}), (None, {"A", "B", "C", "D"})],
)
def test_walk_stops_at_the_given_depth(depth, expected):
    chain = [
        need("A", links=["B"]),
        need("B", links=["C"], incoming=["A"]),
        need("C", links=["D"], incoming=["B"]),
        need("D", incoming=["C"]),
    ]
    assert (
        set(filter_by_tree(view(*chain), "A", ["links"], "outgoing", depth)) == expected
    )


def test_walk_terminates_on_a_cycle():
    """A need already reached is not walked again, so a cycle cannot loop forever."""
    a = need("A", links=["B"], incoming=["C"])
    b = need("B", links=["C"], incoming=["A"])
    c = need("C", links=["A"], incoming=["B"])
    assert set(filter_by_tree(view(a, b, c), "A", ["links"], "outgoing", None)) == {
        "A",
        "B",
        "C",
    }


def test_walk_ignores_link_types_it_was_not_given():
    a = need("A", links=["B"], blocks=["C"])
    assert set(
        filter_by_tree(view(a, need("B"), need("C")), "A", ["links"], "outgoing", None)
    ) == {"A", "B"}


def test_walk_ignores_links_to_needs_outside_the_view():
    """A link to a need that no longer exists is a dead link, not a graph node."""
    a = need("A", links=["GONE"])
    assert set(filter_by_tree(view(a), "A", ["links"], "outgoing", None)) == {"A"}


# --- the allowed link types ----------------------------------------------------------


def _schema(*names: str) -> FieldsSchema:
    schema = FieldsSchema()
    for name in names:
        schema.add_link_field(link_schema(name))
    return schema


def _config(**values: Any) -> NeedsSphinxConfig:
    config = Mock(spec=NeedsSphinxConfig)
    config.flow_link_types = ["links"]
    config.filter_data = {}
    config.variant_data_proxy = None
    config.variants = {}
    for key, value in values.items():
        setattr(config, key, value)
    return config


def test_allowed_link_types_defaults_to_every_type_the_option_lists():
    allowed = resolve_link_types(
        flow(link_types=["links", "blocks"]),
        schema=_schema("links", "blocks", "checks"),
        config=_config(),
        location=nodes.paragraph(),
    )
    assert [link.name for link in allowed] == ["links", "blocks"]


def test_allowed_link_types_matches_names_case_insensitively():
    allowed = resolve_link_types(
        flow(link_types=["LINKS"]),
        schema=_schema("links", "blocks"),
        config=_config(),
        location=nodes.paragraph(),
    )
    assert [link.name for link in allowed] == ["links"]


def test_allowed_link_types_never_includes_parent_needs():
    """Nesting already shows the hierarchy, so a parent link is never drawn as an edge."""
    allowed = resolve_link_types(
        flow(link_types=["links", "parent_needs"]),
        schema=_schema("links", "parent_needs"),
        config=_config(),
        location=nodes.paragraph(),
    )
    assert [link.name for link in allowed] == ["links"]


def test_allowed_link_types_warns_about_an_unknown_name():
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    module_logger = logging.getLogger("sphinx.sphinx_needs.directives.needflow._model")
    handler = _Capture(level=logging.WARNING)
    module_logger.addHandler(handler)
    old_level = module_logger.level
    module_logger.setLevel(logging.WARNING)
    try:
        allowed = resolve_link_types(
            flow(link_types=["links", "BOGUS"]),
            schema=_schema("links"),
            config=_config(),
            location=nodes.paragraph(),
        )
    finally:
        module_logger.removeHandler(handler)
        module_logger.setLevel(old_level)

    assert [link.name for link in allowed] == ["links"]
    assert any(
        "Unknown link type BOGUS in needflow needflow-index-0" in record.getMessage()
        for record in records
    )


def test_allowed_link_types_falls_back_to_the_configuration():
    """Without the option, the (unreachable) ``needs_flow_link_types`` fallback applies."""
    allowed = resolve_link_types(
        flow(link_types=[]),
        schema=_schema("links", "blocks"),
        config=_config(flow_link_types=["blocks"]),
        location=nodes.paragraph(),
    )
    assert [link.name for link in allowed] == ["blocks"]


# --- the presentation of a need ------------------------------------------------------


def _presentation(item, **options: Any) -> NodePresentation:
    return resolve_presentation(
        item,
        highlight=options.pop("highlight", ""),
        border_color=options.pop("border_color", None),
        origin_docname=options.pop("origin_docname", None),
        config=_config(**options),
        needs=[item],
        location=nodes.paragraph(),
    )


def test_presentation_takes_the_style_and_color_of_the_need_type():
    presentation = _presentation(need("A", type_style="card", type_color="#FEDCD2"))
    assert presentation.type_style == "card"
    assert presentation.type_color == "#FEDCD2"


def test_presentation_of_a_type_without_a_color_has_no_color():
    """An empty color is no color, not a color named after the empty string."""
    assert _presentation(need("A", type_color="")).type_color is None


def test_presentation_of_a_need_part_is_always_a_rectangle():
    item = need("A", parts=("p1",)).get_part_item("p1")
    presentation = _presentation(item)
    assert presentation.type_style == "rectangle"


def test_presentation_highlights_a_need_that_passes_the_filter():
    presentation = _presentation(need("A", type="story"), highlight="type == 'story'")
    assert presentation.highlight is True


def test_presentation_does_not_highlight_a_need_that_fails_the_filter():
    presentation = _presentation(need("A", type="story"), highlight="type == 'spec'")
    assert presentation.highlight is False


def test_presentation_highlights_a_need_of_the_origin_document():
    """``c.this_doc()`` resolves against the document the needflow is written in."""
    presentation = _presentation(
        need("A", docname="index"), highlight="c.this_doc()", origin_docname="index"
    )
    assert presentation.highlight is True


def test_presentation_does_not_highlight_a_need_of_another_document():
    presentation = _presentation(
        need("A", docname="page"), highlight="c.this_doc()", origin_docname="index"
    )
    assert presentation.highlight is False


def test_presentation_highlight_without_an_origin_document_is_invalid():
    """Without an origin document ``c.this_doc()`` has nothing to compare against.

    Every caller in the code base passes one, but the parameter is optional, so this
    pins that the failure is the explicit one rather than a silent False.
    """
    with pytest.raises(NeedsInvalidFilter, match="this_doc"):
        _presentation(need("A", docname="index"), highlight="c.this_doc()")


def test_presentation_resolves_the_border_color():
    assert _presentation(need("A"), border_color="FF0000").border_color == "FF0000"


def test_presentation_strips_a_leading_hash_from_the_border_color():
    """Each engine adds the prefix its own syntax needs, so the model holds neither."""
    assert _presentation(need("A"), border_color="#FF0000").border_color == "FF0000"


def test_presentation_border_color_of_an_unmatched_variant_is_none():
    item = need("A", type="story")
    assert (
        _presentation(item, border_color="[type == 'spec']:FF0000").border_color is None
    )


def test_presentation_highlight_wins_over_the_border_color():
    """A highlighted need gets no border color at all, rather than both."""
    presentation = _presentation(
        need("A", type="story"), highlight="type == 'story'", border_color="FF0000"
    )
    assert presentation.highlight is True
    assert presentation.border_color is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("#", None),
        ("FF0000", "FF0000"),
        ("#FF0000", "FF0000"),
        ("  #FF0000  ", "FF0000"),
        (False, "False"),
    ],
)
def test_resolve_color(value, expected):
    assert resolve_color(value) == expected


# --- the node tree -------------------------------------------------------------------


def _tree(*needs) -> tuple[list[GraphNode], dict[str, GraphNode]]:
    return build_node_tree(
        list(needs),
        lambda n: NodePresentation(
            type_style="node", type_color=None, highlight=False, border_color=None
        ),
    )


def test_root_needs_are_the_needs_without_a_parent_in_the_result():
    parent = need("P", children=["C"])
    child = need("C", parent="P")
    assert [n["id"] for n in get_root_needs([parent, child])] == ["P"]
    assert [n["id"] for n in get_root_needs([child])] == ["C"]


def test_root_needs_never_include_a_need_part():
    parent = need("P", parts=("p1",))
    part = parent.get_part_item("p1")
    assert [n["id"] for n in get_root_needs([parent, part])] == ["P"]


def test_tree_nests_children_and_parts_of_the_result():
    parent = need("P", children=["C"], parts=("p1", "p2"))
    child = need("C", parent="P")
    roots, drawn = _tree(parent, parent.get_part_item("p1"), child)

    assert [root.need["id"] for root in roots] == ["P"]
    assert [part.need["id_complete"] for part in roots[0].parts] == ["P.p1"]
    assert [c.need["id"] for c in roots[0].children] == ["C"]
    assert set(drawn) == {"P", "P.p1", "C"}


def test_tree_omits_children_and_parts_that_were_filtered_out():
    """What is drawn follows the result, even though the *nesting block* does not."""
    parent = need("P", children=["C"], parts=("p1",))
    roots, drawn = _tree(parent)
    assert roots[0].parts == []
    assert roots[0].children == []
    assert set(drawn) == {"P"}


def test_tree_does_not_draw_a_part_whose_need_was_filtered_out():
    parent = need("P", parts=("p1",))
    roots, drawn = _tree(parent.get_part_item("p1"))
    assert roots == []
    assert drawn == {}


def test_tree_nests_grandchildren():
    parent = need("P", children=["C"])
    child = need("C", parent="P", children=["G"])
    grandchild = need("G", parent="C")
    roots, drawn = _tree(parent, child, grandchild)
    assert [g.need["id"] for g in roots[0].children[0].children] == ["G"]
    assert set(drawn) == {"P", "C", "G"}


# --- the edges -----------------------------------------------------------------------


def test_edges_are_collected_per_need_and_link_type():
    a = need("A", links=["B"], blocks=["B"])
    b = need("B")
    edges = collect_edges(
        [a, b], [link_schema("links"), link_schema("blocks")], {"A", "B"}
    )
    assert [(e.source_id, e.target_id, e.link_type.name) for e in edges] == [
        ("A", "B", "links"),
        ("A", "B", "blocks"),
    ]


def test_edges_to_a_need_outside_the_result_are_dropped():
    """A link whose target was filtered out has nothing to point at."""
    a = need("A", links=["B", "C"])
    edges = collect_edges([a, need("B")], [link_schema()], {"A", "B"})
    assert [e.target_id for e in edges] == ["B"]


def test_edges_of_a_link_type_that_is_not_allowed_are_not_collected():
    a = need("A", links=["B"], blocks=["B"])
    edges = collect_edges([a, need("B")], [link_schema("blocks")], {"A", "B"})
    assert [e.link_type.name for e in edges] == ["blocks"]


def test_edges_record_whether_their_ends_are_drawn():
    """A need part of a filtered out need is in the result, but is not drawn."""
    parent = need("P", parts=("p1",))
    part = parent.get_part_item("p1")
    a = need("A", links=["P.p1"])
    edges = collect_edges([a, part], [link_schema()], {"A"})
    assert len(edges) == 1
    assert edges[0].source_drawn is True
    assert edges[0].target_drawn is False


def test_edges_of_a_need_part_are_marked_as_part_edges():
    parent = need("P", parts=("p1",))
    part = parent.get_part_item("p1")
    a = need("A", links=["P.p1"])
    edges = collect_edges([a, part], [link_schema()], {"A", "P.p1"})
    assert edges[0].is_part is True


def test_edges_between_needs_are_not_part_edges():
    a = need("A", links=["B"])
    edges = collect_edges([a, need("B")], [link_schema()], {"A", "B"})
    assert edges[0].is_part is False


def test_edge_style_is_the_part_style_for_a_part_edge():
    """A part edge takes ``style_part``, a need edge takes ``style``."""
    parent = need("P", parts=("p1",))
    part = parent.get_part_item("p1")
    a = need("A", links=["P.p1", "B"])
    schema = link_schema(style="dashed", style_part="dotted")
    edges = collect_edges([a, part, need("B")], [schema], {"A", "B", "P.p1"})
    styles = {e.target_id: e.style for e in edges}
    assert styles == {"P.p1": "dotted", "B": "dashed"}
