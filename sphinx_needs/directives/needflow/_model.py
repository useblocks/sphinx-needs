"""The engine independent graph model behind a ``needflow``.

Both needflow engines draw the same graph and differ only in the syntax they write it
in.  This module computes that graph exactly once -- which needs are drawn, how they
nest, how each one is presented, and which edges connect them -- so that
:mod:`~sphinx_needs.directives.needflow._plantuml` and
:mod:`~sphinx_needs.directives.needflow._graphviz` are left with nothing but the
emission of their own syntax.

The model holds resolved values, never syntax: a colour is a colour, not ``#FF0000`` or
``line:FF0000``, and the nesting of needs is a tree, not braces or a ``subgraph``.

Frozen accidents
----------------

Several behaviours reproduced here are accidents of the original per-engine
implementations rather than designed semantics.  They are preserved deliberately --
this module exists to make the two engines share one implementation, not to change what
either of them draws -- and are called out at the point where they happen:

- :func:`filter_by_tree` walks depth first, so ``root_depth`` depends on traversal order.
- ``parent_needs`` is dropped from the allowed link types *before* the root walk, so
  ``root_id`` never follows the need hierarchy.
- The root walk runs before the filter, not after it.
- ``show_link_names`` is OR-ed with ``needs_flow_show_links``, so the configuration can
  only ever turn labels on.
- An edge may point at a need that is not drawn as a node (see :class:`GraphEdge`).
"""

from __future__ import annotations

from collections.abc import Callable, Container, Iterable
from dataclasses import dataclass, field
from typing import Literal

from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsFlowType, SphinxNeedsData
from sphinx_needs.filter_common import (
    apply_max_items,
    filter_single_need,
    process_filters,
)
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedPartItem
from sphinx_needs.needs_schema import FieldsSchema, LinkSchema
from sphinx_needs.variants import match_variants
from sphinx_needs.views import NeedsView

from ._options import (
    FlowDirection,
    resolve_direction,
)

LOGGER = get_logger(__name__)

#: The location accepted by the warning machinery of the values resolved here.
LocationType = tuple[str, int | None] | nodes.Element


def filter_by_tree(
    needs_view: NeedsView,
    root_id: str,
    link_names: list[str],
    direction: Literal["both", "incoming", "outgoing"],
    depth: int | None,
) -> NeedsView:
    """Filter all needs by the given ``root_id``,
    and all needs that are connected to the root need by the given ``link_types``, in the given ``direction``.

    .. note:: The frontier is a dict popped from the end, i.e. the walk is depth first,
       and the first visit of a need wins.  A need reachable at two different depths can
       therefore be recorded at the deeper one and have its subtree pruned by ``depth``.
       This makes ``root_depth`` dependent on traversal order; it is kept as is.
    """
    if root_id not in needs_view:
        return needs_view.filter_ids([])
    roots = {root_id: (0, needs_view[root_id])}
    link_prefixes = (
        ("_back",)
        if direction == "incoming"
        else ("",)
        if direction == "outgoing"
        else ("", "_back")
    )
    links_to_process = [link + d for link in link_names for d in link_prefixes]

    need_ids: list[str] = []
    while roots:
        root_id, (root_depth, root) = roots.popitem()
        if root_id in need_ids:
            continue
        if depth is not None and root_depth > depth:
            continue
        need_ids.append(root_id)
        for link_type_name in links_to_process:
            roots.update(
                {
                    i: (root_depth + 1, needs_view[i])
                    for i in root.get(link_type_name, [])
                    if i in needs_view
                }
            )

    return needs_view.filter_ids(need_ids)


def resolve_color(value: None | str | int | float | bool) -> str | None:
    """Normalise a resolved color option value to an engine neutral form.

    A color may be written with or without a leading ``#``, and each engine adds the
    prefix that its own syntax requires, so any leading ``#`` characters are stripped here.
    An unset or empty value means "no color", rather than a color named after the
    string representation of the value.

    :param value: The resolved value of a color option,
        e.g. the return value of :func:`~sphinx_needs.variants.match_variants`.
    :return: The color without a leading ``#``, or ``None`` if no color was given.
    """
    if value is None:
        return None
    return str(value).strip().lstrip("#") or None


def get_root_needs(found_needs: list[NeedItem | NeedPartItem]) -> list[NeedItem]:
    """Select the needs that start a nesting tree.

    A need is a root if it has no parent need, or if its parent is not part of the
    result.  Need parts are never roots: they are only ever drawn inside their need.

    :param found_needs: The needs and need parts that passed the filter.
    :return: The needs to draw at the top level, in the order they were given.
    """
    return_list = []
    for current_need in found_needs:
        if current_need["is_need"] and isinstance(current_need, NeedItem):
            if "parent_need" not in current_need or current_need["parent_need"] == "":
                # need has no parent, we have to add the need to the root needs
                return_list.append(current_need)
            else:
                parent_found: bool = False
                for elements in found_needs:
                    if elements["id"] == current_need["parent_need"]:
                        parent_found = True
                        break
                if not parent_found:
                    return_list.append(current_need)
    return return_list


@dataclass(frozen=True)
class NodePresentation:
    """The resolved presentation of a single drawn need, free of any engine syntax."""

    type_style: str
    """The style name of the need type, or ``rectangle`` for a need part.

    A need part has no style of its own, and both engines happen to spell their fallback
    for one the same way, so the name is shared here rather than left to each engine.
    """

    type_color: str | None
    """The color of the need type as configured, or ``None`` if it has none.

    This is the raw configured value: it may or may not carry a leading ``#``,
    which each engine handles in the way its own syntax requires.
    """

    highlight: bool
    """Whether the need passed the ``highlight`` filter, and so gets a red outline."""

    border_color: str | None
    """The resolved ``border_color``, without a leading ``#``.

    ``None`` if the option was not given, resolved to nothing, or if ``highlight``
    applies -- a highlight always takes precedence over a border color.
    """


@dataclass
class GraphNode:
    """A single drawn need or need part, and everything drawn inside it."""

    need: NeedItem | NeedPartItem
    """The need or need part itself."""

    presentation: NodePresentation
    """How the need is to be presented."""

    parts: list[GraphNode] = field(default_factory=list)
    """The parts of the need that are part of the result, in the order of the need.

    Empty for a need part: parts cannot have parts.
    """

    children: list[GraphNode] = field(default_factory=list)
    """The child needs that are part of the result, in the order of the parent's back links.

    Empty for a need part, which is never recursed into.
    """


@dataclass(frozen=True)
class GraphEdge:
    """A single link between two needs of the result."""

    source_id: str
    """The complete id of the need the link starts at."""

    target_id: str
    """The complete id of the need the link points at."""

    link_type: LinkSchema
    """The link field the link belongs to, carrying its display configuration."""

    is_part: bool
    """Whether either end of the link is a need part, which is styled differently."""

    source_drawn: bool
    """Whether the source need is drawn as a node.

    A need that is part of the result is not necessarily drawn: a need part whose need
    was filtered out has nowhere to be drawn, but its links are still collected here.
    """

    target_drawn: bool
    """Whether the target need is drawn as a node (see :attr:`source_drawn`)."""

    @property
    def style(self) -> str:
        """The configured line style to use for this link."""
        return (
            self.link_type.display.style_part
            if self.is_part
            else self.link_type.display.style
        )


@dataclass
class NeedflowGraph:
    """The complete graph of one needflow, ready to be emitted by any engine."""

    needs: list[NeedItem | NeedPartItem]
    """All needs and need parts that passed the filter, after the ``max_items`` cap."""

    total_needs: int
    """How many needs passed the filter, before the ``max_items`` cap."""

    roots: list[GraphNode]
    """The top level nodes, each carrying the nodes nested inside it."""

    nodes: dict[str, GraphNode]
    """Every drawn node, by complete id, in the order the nodes are drawn."""

    edges: list[GraphEdge]
    """Every link between needs of the result, in the order the engines emit them."""

    show_link_names: bool
    """Whether edges are to be labelled with the link type."""

    direction: FlowDirection
    """The direction the diagram is drawn in, as an intent rather than an engine token.

    Each engine spells this in its own syntax, and degrades it if it must."""

    config_direction: FlowDirection | None
    """The direction the engine configuration already sets, if any.

    An engine needs this to know whether it has to restate a direction in order to
    override the configuration blob it emits first."""


def resolve_link_types(
    attributes: NeedsFlowType,
    /,
    *,
    schema: FieldsSchema,
    config: NeedsSphinxConfig,
    location: nodes.Element,
) -> list[LinkSchema]:
    """Resolve which link fields a needflow may draw.

    Unknown names given to the ``link_types`` option are warned about, but otherwise
    ignored.

    .. note:: ``parent_needs`` is always removed, so that a child need is not linked to
       its parent by an edge as well as by nesting.  This happens *before* the list is
       used for the root walk, so :option:`root_id <needflow:root_id>` cannot follow the
       need hierarchy either; it is kept as is.

    :param attributes: The needflow's options.
    :param schema: The schema holding all link fields.
    :param config: The Sphinx-Needs configuration.
    :param location: Where to report unknown link type names.
    :return: The link fields to draw, in schema order.
    """
    link_type_names = [link.name.upper() for link in schema.iter_link_fields()]
    option_link_types = [link.upper() for link in attributes["link_types"]]
    for lt in option_link_types:
        if lt not in link_type_names:
            log_warning(
                LOGGER,
                "Unknown link type {link_type} in needflow {flow}. Allowed values: {link_types}".format(
                    link_type=lt,
                    flow=attributes["target_id"],
                    link_types=",".join(link_type_names),
                ),
                "needflow",
                location=location,
            )

    # note the `needs_flow_link_types` fallback is unreachable, since the directive
    # always defaults the option to every link type; it is kept as is
    config_link_types = [link.upper() for link in config.flow_link_types]

    allowed_link_types: list[LinkSchema] = []
    for link_field in schema.iter_link_fields():
        # Skip link-type handling, if it is not part of a specified list of allowed link_types or
        # if not part of the overall configuration of needs_flow_link_types
        if (
            attributes["link_types"]
            and link_field.name.upper() not in option_link_types
        ) or (
            not attributes["link_types"]
            and link_field.name.upper() not in config_link_types
        ):
            continue
        # skip creating links from child needs to their own parent need
        if link_field.name == "parent_needs":
            continue
        allowed_link_types.append(link_field)
    return allowed_link_types


def build_graph(
    app: Sphinx,
    attributes: NeedsFlowType,
    allowed_link_types: list[LinkSchema],
    /,
    *,
    location: nodes.Element,
    variant_location: LocationType,
) -> NeedflowGraph:
    """Compute the whole graph of a single needflow.

    The needs are collected by walking out from ``root_id`` (if given), filtering the
    result, and capping it to ``max_items``.  They are then arranged into the nesting
    tree that both engines draw, each drawn need gets its presentation resolved, and the
    links between all needs of the result are collected.

    :param app: The Sphinx application.
    :param attributes: The needflow's options.
    :param allowed_link_types: The link fields to draw, from :func:`resolve_link_types`.
    :param location: Where to report filter problems.
    :param variant_location: Where to report ``border_color`` variant problems.
        The two engines pass different values, which is kept as is.
    :return: The graph to be emitted.
    """
    needs_config = NeedsSphinxConfig(app.config)
    needs_view = SphinxNeedsData(app.env).get_needs_view()

    # the root walk runs before the filter, so a need excluded by the filter can still
    # act as a stepping stone to a need that is included; it is kept as is
    need_values = (
        filter_by_tree(
            needs_view,
            root_id,
            [lt.name for lt in allowed_link_types],
            attributes["root_direction"],
            attributes["root_depth"],
        )
        if (root_id := attributes["root_id"])
        else needs_view
    )
    found_needs = process_filters(
        app,
        need_values,
        attributes,
        origin="needflow",
        location=location,
    )
    # the cap is applied before any of the drawing data is derived,
    # so that dropped needs cannot be referenced by what is drawn
    found_needs, total_needs = apply_max_items(
        found_needs, attributes.get("max_items"), needs_config
    )

    roots, drawn = build_node_tree(
        found_needs,
        lambda need: resolve_presentation(
            need,
            highlight=attributes["highlight"],
            border_color=attributes["border_color"],
            config=needs_config,
            needs=needs_view.values(),
            location=variant_location,
            origin_docname=attributes["docname"],
        ),
    )

    return NeedflowGraph(
        needs=found_needs,
        total_needs=total_needs,
        roots=roots,
        nodes=drawn,
        edges=collect_edges(found_needs, allowed_link_types, drawn),
        # the configuration can only ever turn link names on; it is kept as is
        show_link_names=attributes["show_link_names"] or needs_config.flow_show_links,
        direction=resolve_direction(
            attributes["direction"],
            attributes["config_direction"],
            needs_config.flow_direction,
            location=location,
        ),
        config_direction=attributes["config_direction"],
    )


def resolve_presentation(
    need: NeedItem | NeedPartItem,
    /,
    *,
    highlight: str,
    border_color: str | None,
    config: NeedsSphinxConfig,
    needs: Iterable[NeedItem | NeedPartItem],
    location: LocationType,
    origin_docname: str | None = None,
) -> NodePresentation:
    """Resolve how a single need is to be presented.

    :param need: The need or need part to be drawn.
    :param highlight: The ``highlight`` filter, empty if the option was not given.
    :param border_color: The ``border_color`` option, in variant syntax.
    :param config: The Sphinx-Needs configuration.
    :param needs: All needs, for a ``highlight`` filter that consults them.
    :param location: Where to report ``border_color`` variant problems.
    :param origin_docname: The document the needflow is written in, so that a
        ``highlight`` filter may test the need against it with ``c.this_doc()``.
    :return: The resolved presentation.
    """
    is_highlighted = bool(highlight) and filter_single_need(
        need, config, highlight, needs, origin_docname=origin_docname
    )
    resolved_border = None
    if not is_highlighted and border_color:
        # a highlight always wins, so the border color is not even resolved
        resolved_border = resolve_color(
            match_variants(
                border_color,
                need.filter_context(),
                config.variants,
                location=location,
            )
        )
    return NodePresentation(
        # need parts have no style of their own
        type_style=need["type_style"] if need["is_need"] else "rectangle",
        type_color=need["type_color"] or None,
        highlight=is_highlighted,
        border_color=resolved_border,
    )


def build_node_tree(
    found_needs: list[NeedItem | NeedPartItem],
    presentation: Callable[[NeedItem | NeedPartItem], NodePresentation],
    /,
) -> tuple[list[GraphNode], dict[str, GraphNode]]:
    """Arrange the needs of a result into the tree of nodes that the engines draw.

    A need is drawn inside its parent need, and a need part inside its need, so a need
    whose parent is not part of the result becomes a root, and a need part whose need is
    not part of the result is not drawn at all.

    :param found_needs: The needs and need parts that passed the filter.
    :param presentation: How to resolve the presentation of a single need.
    :return: The root nodes, and every drawn node by complete id.
    """
    found_by_id = {need["id_complete"]: need for need in found_needs}
    drawn: dict[str, GraphNode] = {}

    def _build(need: NeedItem | NeedPartItem, *, leaf: bool = False) -> GraphNode:
        node = GraphNode(need=need, presentation=presentation(need))
        drawn[need["id_complete"]] = node
        if leaf:
            # a need part is never recursed into, by either engine
            return node
        if need["is_need"]:
            for part_id in need["parts"]:
                if (part := found_by_id.get(f"{need['id']}.{part_id}")) is not None:
                    node.parts.append(_build(part, leaf=True))
        for child_id in need["parent_needs_back"]:
            if (child := found_by_id.get(child_id)) is not None:
                node.children.append(_build(child))
        return node

    return [_build(root) for root in get_root_needs(found_needs)], drawn


def collect_edges(
    found_needs: list[NeedItem | NeedPartItem],
    allowed_link_types: list[LinkSchema],
    drawn: Container[str],
    /,
) -> list[GraphEdge]:
    """Collect every link between the needs of a result.

    A link is collected only if its target is part of the result; whether either of its
    ends is actually *drawn* is recorded rather than acted on, since the engines differ
    in what they do with a link that has an undrawn end.

    :param found_needs: The needs and need parts that passed the filter.
    :param allowed_link_types: The link fields to draw.
    :param drawn: The complete ids of the drawn nodes, from :func:`build_node_tree`.
    :return: The edges, in the order the engines emit them.
    """
    # a need and a need part are both identified by their complete id
    found_ids = {need["id_complete"] for need in found_needs}
    edges: list[GraphEdge] = []
    for need in found_needs:
        source_id = need["id_complete"]
        for link_type in allowed_link_types:
            for link in need[link_type.name]:
                if link not in found_ids:
                    # the link target was filtered out, so there is nothing to point at
                    continue
                edges.append(
                    GraphEdge(
                        source_id=source_id,
                        target_id=link,
                        link_type=link_type,
                        is_part="." in link or "." in source_id,
                        source_drawn=source_id in drawn,
                        target_drawn=link in drawn,
                    )
                )
    return edges
