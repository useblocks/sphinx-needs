from __future__ import annotations

import html
import textwrap
from collections.abc import Callable
from functools import cache
from typing import Literal
from urllib.parse import urlparse

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.ext.graphviz import (
    ClickableMapDefinition,
    GraphvizError,
    render_dot,
)
from sphinx.util.logging import getLogger

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.directives.needflow._directive import NeedflowGraphiz
from sphinx_needs.directives.utils import no_needs_found_paragraph, report_max_items
from sphinx_needs.errors import NoUri
from sphinx_needs.logging import log_warning
from sphinx_needs.need_item import NeedItem, NeedPartItem
from sphinx_needs.utils import remove_node_from_tree

from ._model import (
    GraphEdge,
    GraphNode,
    NodePresentation,
    build_graph,
    resolve_link_types,
)
from ._options import GRAPHVIZ_SHAPES, LinkLabels, graphviz_rankdir
from ._shared import create_filter_paragraph, create_legend_nodes

try:
    from sphinx.writers.html5 import HTML5Translator
except ImportError:
    from sphinx.writers.html import HTML5Translator  # type: ignore[attr-defined]

LOGGER = getLogger(__name__)


@measure_time("needflow_graphviz")
def process_needflow_graphviz(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    needs_config = NeedsSphinxConfig(app.config)
    needs_schema = SphinxNeedsData(app.env).get_schema()

    node: NeedflowGraphiz
    for node in found_nodes:  # type: ignore[assignment]
        attributes = node.attributes

        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        if app.builder.format != "html":
            log_warning(
                LOGGER,
                "NeedflowGraphiz is only supported for HTML output.",
                "needflow",
                location=node,
            )
            remove_node_from_tree(node)
            continue

        if attributes["show_filters"]:
            para = create_filter_paragraph(attributes)
            # add the paragraph to after the surrounding figure
            node.parent.parent.insert(node.parent.parent.index(node.parent) + 1, para)

        allowed_link_types = resolve_link_types(
            attributes,
            schema=needs_schema,
            config=needs_config,
            location=node,
        )

        graph = build_graph(
            app,
            attributes,
            allowed_link_types,
            location=node,
            variant_location=node,
        )

        # this check used to run before the `max_items` cap, which the model now applies;
        # the verdict is the same either way, because `apply_max_items` either returns the
        # needs unchanged or truncates them to a limit of at least one, so it can never
        # turn a non-empty result into an empty one
        if not graph.needs:
            node.replace_self(
                no_needs_found_paragraph(attributes.get("filter_warning"))
            )
            continue

        if len(graph.needs) < graph.total_needs:
            para = report_max_items(
                len(graph.needs),
                graph.total_needs,
                origin="needflow",
                location=node,
            )
            # add the paragraph to after the surrounding figure
            node.parent.parent.insert(node.parent.parent.index(node.parent) + 1, para)

        content = "digraph needflow {\ncompound=true;\n"

        # global settings
        for key, value in attributes["graphviz_style"].get("root", {}).items():
            content += f"{key}={_quote(str(value))};\n"

        # the config blob is a preamble of defaults, so the direction is written after
        # it and wins; nothing is written for a diagram already drawn that way
        if (
            rankdir := graphviz_rankdir(graph.direction, graph.config_direction)
        ) is not None:
            content += f"rankdir={_quote(rankdir)};\n"
        for etype in ("graph", "node", "edge"):
            if etype in attributes["graphviz_style"]:
                content += f"{etype} [\n"
                for key, value in attributes["graphviz_style"][etype].items():
                    content += f"  {key}={_quote(str(value))};\n"
                content += "]\n"

        # calculate node definitions
        content += "\n// node definitions\n"
        cluster_ids: dict[str, str | None] = {}
        """A mapping of node id_complete to the cluster id if the node is a subgraph, else None."""
        for root in graph.roots:
            content += _render_node(
                root,
                node,
                lambda n: _get_link_to_need(app, fromdocname, n),
                cluster_ids,
            )

        # calculate edge definitions
        content += "\n// edge definitions\n"
        for edge in graph.edges:
            content += _render_edge(edge, graph.link_labels, cluster_ids)

        # note this lists only the need types that were actually drawn, whereas the
        # plantuml engine lists every configured type, so the same `:show_legend:` gives
        # the two engines different legends; it is kept as is
        if attributes["show_legend"]:
            content += _create_legend(
                [drawn.need for drawn in graph.nodes.values()], needs_config
            )

        content += "}"

        node["resolved_content"] = content

        if attributes["debug"]:
            code = nodes.literal_block(
                content, content, language="dot", linenos=True, force=True
            )
            code.source, code.line = node.source, node.line
            # add the debug code to after the surrounding figure
            node.parent.parent.insert(node.parent.parent.index(node.parent) + 1, code)

        # the portable legend is a document table beside the diagram, identical on
        # every engine, rather than part of the picture; inserted last so that it ends
        # up directly below the figure it describes
        for legend in create_legend_nodes(
            graph.legend, graph.drawn_types, graph.drawn_link_types
        ):
            node.parent.parent.insert(node.parent.parent.index(node.parent) + 1, legend)


def _get_link_to_need(
    app: Sphinx, docname: str, need_info: NeedItem | NeedPartItem
) -> str | None:
    """Compute the link to a need, relative to a document.

    It is of note that the links are computed relative to the document that the graph is in.
    For PNGs, the links are defined as https://developer.mozilla.org/en-US/docs/Web/HTML/Element/map in the document, so this correct.
    For SVGs, the graphs are extracted to external files, and in this case the links are modified to be relative to the SVG file
    (from sphinx 7.2 onwards, see: https://github.com/sphinx-doc/sphinx/pull/11078)
    """
    if need_info["is_external"]:
        if need_info["external_url"] and urlparse(need_info["external_url"]).scheme:
            return need_info["external_url"]
    elif need_info["docname"]:
        try:
            rel_uri = app.builder.get_relative_uri(docname, need_info["docname"])
            if not rel_uri:
                # svg relative path fix cannot yet handle empty paths https://github.com/sphinx-doc/sphinx/issues/13078
                rel_uri = app.builder.get_target_uri(docname.split("/")[-1])
        except NoUri:
            return None
        return rel_uri + "#" + need_info["id_complete"]
    return None


def _quote(text: str) -> str:
    """Quote a string for use in a graphviz file."""
    return '"' + text.replace('"', '\\"') + '"'


def _render_node(
    drawn: GraphNode,
    node: NeedflowGraphiz,
    calc_link: Callable[[NeedItem | NeedPartItem], str | None],
    cluster_ids: dict[str, str | None],
    subgraph: bool = True,
) -> str:
    """Render a node in the graphviz format.

    :param drawn: The node to render, carrying its resolved presentation.
    :param node: The needflow node, for the graphviz style of the whole diagram.
    :param calc_link: How to compute the link target of a need.
    :param cluster_ids: Collects the cluster id of every node drawn as a subgraph,
        which the edges need in order to point at the cluster rather than the ghost node.
    """
    if subgraph and (drawn.parts or drawn.children):
        # graphviz cannot nest nodes,
        # so we have to create a subgraph to represent a need with parts/children
        return _render_subgraph(drawn, node, calc_link, cluster_ids)

    need = drawn.need
    presentation = drawn.presentation
    cluster_ids[need["id_complete"]] = None

    params: list[tuple[str, str]] = []

    # label
    params.append(("label", _label(need, "left")))
    params.append(("tooltip", _quote(need["id_complete"])))

    # link
    if _link := calc_link(need):
        params.extend([("href", _quote(_link)), ("target", _quote("_top"))])

    # shape
    if presentation.styles.shape:
        params.append(("shape", _quote(GRAPHVIZ_SHAPES[presentation.styles.shape])))
    elif need["is_need"]:
        if presentation.type_style not in _plantuml_shapes:
            log_warning(
                LOGGER,
                f"Unknown node style {presentation.type_style!r} for graphviz engine",
                "needflow",
                None,
                once=True,
            )
        shape = _plantuml_shapes.get(presentation.type_style, presentation.type_style)
        params.append(("shape", _quote(shape)))
    else:
        params.append(("shape", "rectangle"))

    params.extend(
        _presentation_params(
            presentation,
            base_style=node.attributes["graphviz_style"].get("node", {}).get(
                "style", ""
            ),
        )
    )

    id = _quote(need["id_complete"])
    param_str = ", ".join(f"{key}={value}" for key, value in params)
    return f"{id} [{param_str}];\n"


def _render_subgraph(
    drawn: GraphNode,
    node: NeedflowGraphiz,
    calc_link: Callable[[NeedItem | NeedPartItem], str | None],
    cluster_ids: dict[str, str | None],
) -> str:
    """Render a need with parts or child needs, as a graphviz subgraph.

    .. note:: The shape of a need drawn as a subgraph is emitted as configured, without
       the translation (and the warning) that a plain node gets; it is kept as is.

    :param drawn: The node to render, carrying the nodes nested inside it.
    :param node: The needflow node, for the graphviz style of the whole diagram.
    :param calc_link: How to compute the link target of a need.
    :param cluster_ids: See :func:`_render_node`.
    """
    need = drawn.need
    presentation = drawn.presentation
    params: list[tuple[str, str]] = []

    # label
    params.append(("label", _label(need, "center")))
    params.append(("tooltip", _quote(need["id_complete"])))

    # link
    if _link := calc_link(need):
        params.extend([("href", _quote(_link)), ("target", _quote("_top"))])

    # shape
    if presentation.styles.shape:
        params.append(("shape", _quote(GRAPHVIZ_SHAPES[presentation.styles.shape])))
    elif need["is_need"]:
        params.append(("shape", _quote(presentation.type_style)))
    else:
        params.append(("shape", "rectangle"))

    params.extend(_presentation_params(presentation, base_style=""))

    # we need to create an invisible node to allow links to the subgraph
    id = _quote(need["id_complete"])
    ghost_node = f'{id} [style=invis, width=0, height=0, label=""];'

    cluster_id = _quote("cluster_" + need["id_complete"])
    param_str = "\n".join(f"  {key}={value};" for key, value in params)

    cluster_ids[need["id_complete"]] = "cluster_" + need["id_complete"]

    # note the comments are written according to the need itself, not to what is drawn,
    # so a need whose parts were all filtered out still gets the parts comment
    children = ""
    if need["is_need"] and need["parts"]:
        children += "  // parts:\n"
        for part in drawn.parts:
            children += textwrap.indent(
                _render_node(part, node, calc_link, cluster_ids, False), "  "
            )
    if need["parent_needs_back"]:
        children += "  // child needs:\n"
        for child in drawn.children:
            children += textwrap.indent(
                _render_node(child, node, calc_link, cluster_ids), "  "
            )

    return f"subgraph {cluster_id} {{\n{param_str}\n\n  {ghost_node}\n{children}\n}};\n"


def _presentation_params(
    presentation: NodePresentation, *, base_style: str
) -> list[tuple[str, str]]:
    """Render the fill, outline and text of a node as graphviz attributes.

    Both the plain node path and the subgraph path go through here, so that the two
    cannot quietly grow apart again the way they had before.  Only the shape is left
    to the callers, which still differ in whether they translate it.

    A style rule wins over the configured need type, and a highlight wins over both --
    unless a later rule set an outline of its own, which the model has already resolved.

    :param presentation: The resolved presentation of the node.
    :param base_style: The diagram-wide graphviz ``node`` style to keep alongside
        ``filled``, empty if there is none to keep.
    :return: The attributes to add, in emission order.
    """
    styles = presentation.styles
    params: list[tuple[str, str]] = []

    # a configured type color is used verbatim, since it may be a color *name*; a style
    # rule's color has been normalised to bare hex, so it gets the "#" back here
    fill: str | None = None
    if styles.fill:
        fill = "#" + styles.fill
    elif presentation.type_color:
        fill = presentation.type_color

    style_entries: list[str] = []
    if fill:
        if base_style:
            style_entries.append(base_style)
        style_entries.append("filled")
    if styles.shape == "rounded":
        # graphviz draws a rounded box as a box with a style, not as a shape of its own
        style_entries.append("rounded")
    if styles.border_style in ("dashed", "dotted"):
        style_entries.append(styles.border_style)
    if style_entries:
        params.append(("style", _quote(",".join(style_entries))))
    if fill:
        params.append(("fillcolor", _quote(fill)))

    if presentation.highlight:
        params.append(("color", "red"))
    elif styles.border:
        params.append(("color", _quote("#" + styles.border)))
    elif presentation.border_color:
        params.append(("color", _quote("#" + presentation.border_color)))

    if styles.border_width is not None:
        params.append(("penwidth", str(styles.border_width)))
    if styles.text_color:
        params.append(("fontcolor", _quote("#" + styles.text_color)))

    return params


def _label(
    need: NeedItem | NeedPartItem, align: Literal["left", "right", "center"]
) -> str:
    """Create the graphviz label for a need."""
    # note this is based on the plantuml template DEFAULT_DIAGRAM_TEMPLATE

    br = f'<br align="{align}"/>'
    # note this text wrapping mimics the jinja wordwrap filter
    need_title = need["title"] if need["is_need"] else need["content"]
    title = br.join(
        br.join(
            textwrap.wrap(
                html.escape(line),
                15,
                expand_tabs=False,
                replace_whitespace=False,
                break_long_words=True,
                break_on_hyphens=True,
            )
        )
        for line in need_title.splitlines()
    )
    name = html.escape(need["type_name"] + (" (part)" if need["is_part"] else ""))
    if need["is_need"]:
        _id = html.escape(need["id"])
    else:
        _id = f'{html.escape(need["id_parent"])}.<b align="{align}">{html.escape(need["id"])}</b>'
    font_10 = '<font point-size="10">'
    font_12 = '<font point-size="12">'
    return f"<{font_12}{name}</font>{br}<b>{title}</b>{br}{font_10}{_id}</font>{br}>"


def _render_edge(
    edge: GraphEdge,
    link_labels: LinkLabels,
    cluster_ids: dict[str, str | None],
) -> str:
    """Render an edge in the graphviz format.

    :param edge: The edge to render.
    :param link_labels: What to label the edge with, if anything.
    :param cluster_ids: The cluster ids collected by :func:`_render_node`.
    """
    if not (edge.source_drawn and edge.target_drawn):
        # if the start or end node is not rendered, we should not create a link
        return ""

    params: list[tuple[str, str]] = []

    if (label := edge.label(link_labels)) is not None:
        params.append(("label", _quote(label)))

    params.extend(
        # TODO also use link_type.display.color?
        _style_params_from_link_type(
            edge.style,
            edge.link_type.display.style_start,
            edge.link_type.display.style_end,
        )
    )

    start_id = _quote(edge.source_id)
    if (ltail := cluster_ids[edge.source_id]) is not None:
        # the need has been created as a subgraph and so we also need to create a logical link to the cluster
        params.append(("ltail", _quote(ltail)))

    end_id = _quote(edge.target_id)
    if (lhead := cluster_ids[edge.target_id]) is not None:
        # the end need has been created as a subgraph and so we also need to create a logical link to the cluster
        params.append(("lhead", _quote(lhead)))

    param_str = ", ".join(f"{key}={value}" for key, value in params)
    return f"{start_id} -> {end_id} [{param_str}];\n"


@cache
def _style_params_from_link_type(
    styles: str, style_start: str, style_end: str
) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []

    for style in styles.split(","):
        if not (style := style.strip()):
            continue
        if style.startswith("#"):
            # assume this is a color
            params.append(("color", _quote(style)))
        elif style in ("dotted", "dashed", "solid", "bold"):
            params.append(("style", _quote(style)))
        else:
            log_warning(
                LOGGER,
                f"Unknown link style {style!r} for graphviz engine",
                "needflow",
                None,
                once=True,
            )

    # convert plantuml arrow start/end style to graphviz style.
    plantuml_arrow_ends = style_start + style_end
    # we are going to cheat a bit here and only look at the start and end characters
    # this means we ignore things like the direction of the arrow, e.g. `-up->`
    plantuml_arrow_ends = plantuml_arrow_ends[0] + plantuml_arrow_ends[-1]
    if (arrow_style := _plantuml_arrow_style.get(plantuml_arrow_ends)) is None:
        log_warning(
            LOGGER,
            f"Unknown link start/end style {plantuml_arrow_ends!r} for graphviz engine",
            "needflow",
            None,
            once=True,
        )
    else:
        params.extend(arrow_style)

    return params


# in plantuml guide, see: 8.7 "Nestable elements"
# we try to match most to https://graphviz.org/doc/info/shapes.html
_plantuml_shapes = {
    "agent": "box",
    "artifact": "note",
    "card": "box",
    "component": "component",
    "database": "cylinder",
    "file": "note",
    "folder": "folder",
    "frame": "tab",
    "hexagon": "hexagon",
    "node": "box3d",
    "package": "folder",
    "queue": "cylinder",
    "rectangle": "rectangle",
    "stack": "rectangle",
    "storage": "ellipse",
    "usecase": "oval",
}

# in plantuml guide, see: "8.13.1 Type of arrow head"
# we try to match most to https://graphviz.org/doc/info/arrows.html
# note -->> would actually be the normal style in graphviz
_plantuml_arrow_style = {
    # neither
    "--": (("arrowhead", "none"),),
    # head only
    "->": (("arrowhead", "vee"),),
    "-*": (("arrowhead", "diamond"),),
    "-o": (("arrowhead", "odiamond"),),
    "-O": (("arrowhead", "odot"),),
    "-@": (("arrowhead", "dot"),),
    # tail only
    "<-": (("dir", "back"), ("arrowtail", "vee")),
    "*-": (("dir", "back"), ("arrowtail", "diamond")),
    "o-": (("dir", "back"), ("arrowtail", "odiamond")),
    "O-": (("dir", "back"), ("arrowtail", "odot")),
    "@-": (("dir", "back"), ("arrowtail", "dot")),
    # both same
    "<>": (("dir", "both"), ("arrowtail", "vee"), ("arrowhead", "vee")),
    "**": (("dir", "both"), ("arrowtail", "diamond"), ("arrowhead", "diamond")),
    "oo": (("dir", "both"), ("arrowtail", "odiamond"), ("arrowhead", "odiamond")),
    "OO": (("dir", "both"), ("arrowtail", "odot"), ("arrowhead", "odot")),
    "@@": (("dir", "both"), ("arrowtail", "dot"), ("arrowhead", "dot")),
    # both different
    "*>": (("dir", "both"), ("arrowtail", "diamond"), ("arrowhead", "vee")),
    "o>": (("dir", "both"), ("arrowtail", "odiamond"), ("arrowhead", "vee")),
    "O>": (("dir", "both"), ("arrowtail", "odot"), ("arrowhead", "vee")),
    "@>": (("dir", "both"), ("arrowtail", "dot"), ("arrowhead", "vee")),
    "<*": (("dir", "both"), ("arrowtail", "vee"), ("arrowhead", "diamond")),
    "<o": (("dir", "both"), ("arrowtail", "vee"), ("arrowhead", "odiamond")),
    "<O": (("dir", "both"), ("arrowtail", "vee"), ("arrowhead", "odot")),
    "<@": (("dir", "both"), ("arrowtail", "vee"), ("arrowhead", "dot")),
    "o*": (("dir", "both"), ("arrowtail", "odiamond"), ("arrowhead", "diamond")),
    "O*": (("dir", "both"), ("arrowtail", "odot"), ("arrowhead", "diamond")),
    "@*": (("dir", "both"), ("arrowtail", "dot"), ("arrowhead", "diamond")),
    "*o": (("dir", "both"), ("arrowtail", "diamond"), ("arrowhead", "odiamond")),
    "Oo": (("dir", "both"), ("arrowtail", "odot"), ("arrowhead", "odiamond")),
    "@o": (("dir", "both"), ("arrowtail", "dot"), ("arrowhead", "odiamond")),
    "*O": (("dir", "both"), ("arrowtail", "diamond"), ("arrowhead", "odot")),
    "oO": (("dir", "both"), ("arrowtail", "odiamond"), ("arrowhead", "odot")),
    "@O": (("dir", "both"), ("arrowtail", "dot"), ("arrowhead", "odot")),
    "*@": (("dir", "both"), ("arrowtail", "diamond"), ("arrowhead", "dot")),
    "o@": (("dir", "both"), ("arrowtail", "odiamond"), ("arrowhead", "dot")),
    "O@": (("dir", "both"), ("arrowtail", "odot"), ("arrowhead", "dot")),
}


def _create_legend(
    needs: list[NeedItem | NeedPartItem], config: NeedsSphinxConfig
) -> str:
    """Create a legend for the graph."""

    # TODO also show links in legend

    # filter types by ones that are actually used
    types = {need["type"] for need in needs}
    need_types = [ntype for ntype in config.types if ntype["directive"] in types]

    label = '<<TABLE border="0">'
    label += '\n<TR><TD align="center"><B>Legend</B></TD></TR>'

    for need_type in need_types:
        title = html.escape(need_type["title"])
        # 'color' is optional, and a type without one keeps its row,
        # without a background color, rather than being dropped from the legend
        if color := need_type.get("color"):
            label += f'\n<TR><TD align="left" bgcolor={_quote(color)}>{title}</TD></TR>'
        else:
            label += f'\n<TR><TD align="left">{title}</TD></TR>'

    label += "\n</TABLE>>"

    legend = f"""
{{
    rank = sink;
    legend [
        shape=box,
        style=rounded,
        label={label}
    ];
}}
"""
    return legend


def html_visit_needflow_graphviz(self: HTML5Translator, node: NeedflowGraphiz) -> None:
    """This visitor closely mimics ``sphinx.ext.graphviz.html_visit_graphviz``,
    however, that is not used directly due to these current key differences:

    - The warning is changed, to give the location of the source directive
    - svg's are output as ``<img>`` tags, not ``<object>`` tags (allows e.g. for transparency)
    - svg's are wrapped in an `<a>` tag, to allow for linking to the svg file
    """
    code = node.get("resolved_content")
    if code is None:
        log_warning(LOGGER, "Content has not been resolved", "needflow", location=node)
        raise nodes.SkipNode
    attrributes = node.attributes
    format: Literal["png", "svg"] = self.builder.config.graphviz_output_format
    if format not in ("png", "svg"):
        log_warning(
            LOGGER,
            f"graphviz_output_format must be one of 'png', 'svg', but is {format!r}",
            "needflow",
            None,
            once=True,
        )
        raise nodes.SkipNode
    try:
        fname, outfn = render_dot(
            self, code, {"docname": attrributes["docname"]}, format, "needflow"
        )
    except GraphvizError as exc:
        log_warning(
            LOGGER,
            f"graphviz code failed to render (run with :debug: to see code): {exc}",
            "needflow",
            location=node,
        )
        raise nodes.SkipNode from exc

    classes = ["graphviz", *attrributes.get("classes", [])]
    imgcls = " ".join(filter(None, classes))

    if fname is None:
        self.body.append(self.encode(code))
    else:
        alt = attrributes["alt"]
        if alt is None:
            # the author did not describe the diagram, so give it a generic description
            alt = "needflow graphviz diagram"
        if "align" in attrributes:
            self.body.append(
                f'<div align="{attrributes["align"]}" class="align-{attrributes["align"]}">'
            )
        if format == "svg":
            self.body.append('<div class="graphviz">\n')
            self.body.append(f'<a href="{fname}">\n')
            self.body.append(
                f'<img src="{fname}" alt="{alt}" class="{imgcls}"></img>\n'
            )
            self.body.append("</a>\n")
            self.body.append("</div>\n")
        else:
            assert outfn is not None
            with open(outfn + ".map", encoding="utf-8") as mapfile:
                imgmap = ClickableMapDefinition(
                    outfn + ".map", mapfile.read(), dot=code
                )
                if imgmap.clickable:
                    # has a map
                    self.body.append('<div class="graphviz">')
                    self.body.append(
                        f'<img src="{fname}" alt="{alt}" usemap="#{imgmap.id}" class="{imgcls}" />'
                    )
                    self.body.append("</div>\n")
                    self.body.append(imgmap.generate_clickable_map())
                else:
                    # nothing in image map
                    self.body.append('<div class="graphviz">')
                    self.body.append(
                        f'<img src="{fname}" alt="{alt}" class="{imgcls}" />'
                    )
                    self.body.append("</div>\n")
        if "align" in attrributes:
            self.body.append("</div>\n")

    raise nodes.SkipNode
