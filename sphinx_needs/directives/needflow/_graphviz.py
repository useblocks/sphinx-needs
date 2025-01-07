from __future__ import annotations

import html
import textwrap
from functools import cache
from typing import Callable, Literal, TypedDict
from urllib.parse import urlparse

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.ext.graphviz import (
    ClickableMapDefinition,
    GraphvizError,
    render_dot,
)
from sphinx.util.logging import getLogger

from sphinx_needs.config import LinkOptionsType, NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.directives.needflow._directive import NeedflowGraphiz
from sphinx_needs.directives.utils import no_needs_found_paragraph
from sphinx_needs.errors import NoUri
from sphinx_needs.filter_common import (
    filter_single_need,
    process_filters,
)
from sphinx_needs.logging import log_warning
from sphinx_needs.utils import (
    match_variants,
    remove_node_from_tree,
)
from sphinx_needs.views import NeedsView

from ._shared import create_filter_paragraph, filter_by_tree, get_root_needs

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
    env_data = SphinxNeedsData(app.env)
    needs_view = env_data.get_needs_view()

    link_type_names = [link["option"].upper() for link in needs_config.extra_links]
    allowed_link_types_options = [link.upper() for link in needs_config.flow_link_types]

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
                    None,
                )

        # compute the allowed link names
        allowed_link_types: list[LinkOptionsType] = []
        for link_type in needs_config.extra_links:
            # Skip link-type handling, if it is not part of a specified list of allowed link_types or
            # if not part of the overall configuration of needs_flow_link_types
            if (
                attributes["link_types"]
                and link_type["option"].upper() not in option_link_types
            ) or (
                not attributes["link_types"]
                and link_type["option"].upper() not in allowed_link_types_options
            ):
                continue
            # skip creating links from child needs to their own parent need
            if link_type["option"] == "parent_needs":
                continue
            allowed_link_types.append(link_type)

        init_filtered_needs = (
            filter_by_tree(
                needs_view,
                root_id,
                allowed_link_types,
                attributes["root_direction"],
                attributes["root_depth"],
            )
            if (root_id := attributes["root_id"])
            else needs_view
        )
        filtered_needs = process_filters(
            app,
            init_filtered_needs,
            node.attributes,
            origin="needflow",
            location=node,
        )

        if not filtered_needs:
            node.replace_self(
                no_needs_found_paragraph(attributes.get("filter_warning"))
            )
            continue

        id_comp_to_need = {need["id_complete"]: need for need in filtered_needs}

        content = "digraph needflow {\ncompound=true;\n"

        # global settings
        for key, value in attributes["graphviz_style"].get("root", {}).items():
            content += f"{key}={_quote(str(value))};\n"
        for etype in ("graph", "node", "edge"):
            if etype in attributes["graphviz_style"]:
                content += f"{etype} [\n"
                for key, value in attributes["graphviz_style"][etype].items():
                    content += f"  {key}={_quote(str(value))};\n"
                content += "]\n"

        # calculate node definitions
        content += "\n// node definitions\n"
        rendered_nodes: dict[str, _RenderedNode] = {}
        """A mapping of node id_complete to the cluster id if the node is a subgraph, else None."""
        for root_need in get_root_needs(filtered_needs):
            content += _render_node(
                root_need,
                node,
                needs_view,
                needs_config,
                lambda n: _get_link_to_need(app, fromdocname, n),
                id_comp_to_need,
                rendered_nodes,
            )

        # calculate edge definitions
        content += "\n// edge definitions\n"
        for need in filtered_needs:
            for link_type in allowed_link_types:
                for link in need[link_type["option"]]:  # type: ignore[literal-required]
                    content += _render_edge(
                        need, link, link_type, node, needs_config, rendered_nodes
                    )

        if attributes["show_legend"]:
            content += _create_legend(
                [r["need"] for r in rendered_nodes.values()], needs_config
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


def _get_link_to_need(
    app: Sphinx, docname: str, need_info: NeedsInfoType
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


class _RenderedNode(TypedDict):
    cluster_id: str | None
    need: NeedsInfoType


def _quote(text: str) -> str:
    """Quote a string for use in a graphviz file."""
    return '"' + text.replace('"', '\\"') + '"'


def _render_node(
    need: NeedsInfoType,
    node: NeedflowGraphiz,
    needs_view: NeedsView,
    config: NeedsSphinxConfig,
    calc_link: Callable[[NeedsInfoType], str | None],
    id_comp_to_need: dict[str, NeedsInfoType],
    rendered_nodes: dict[str, _RenderedNode],
    subgraph: bool = True,
) -> str:
    """Render a node in the graphviz format."""

    if subgraph and (
        (
            need["is_need"]
            and any(f"{need['id']}.{i}" in id_comp_to_need for i in need["parts"])
        )
        or any(i in id_comp_to_need for i in need["parent_needs_back"])
    ):
        # graphviz cannot nest nodes,
        # so we have to create a subgraph to represent a need with parts/children
        return _render_subgraph(
            need, node, needs_view, config, calc_link, id_comp_to_need, rendered_nodes
        )

    rendered_nodes[need["id_complete"]] = {"need": need, "cluster_id": None}

    params: list[tuple[str, str]] = []

    # label
    params.append(("label", _label(need, "left")))
    params.append(("tooltip", _quote(need["id_complete"])))

    # link
    if _link := calc_link(need):
        params.extend([("href", _quote(_link)), ("target", _quote("_top"))])

    # shape
    if need["is_need"]:
        if need["type_style"] not in _plantuml_shapes:
            log_warning(
                LOGGER,
                f"Unknown node style {need['type_style']!r} for graphviz engine",
                "needflow",
                None,
                once=True,
            )
        shape = _plantuml_shapes.get(need["type_style"], need["type_style"])
        params.append(("shape", _quote(shape)))
    else:
        params.append(("shape", "rectangle"))

    # fill color
    if need["type_color"]:
        style = node.attributes["graphviz_style"].get("node", {}).get("style", "")
        new_style = style + ",filled" if style else "filled"
        params.append(("style", _quote(new_style)))
        params.append(("fillcolor", _quote(need["type_color"])))

    # outline color
    if node["highlight"] and filter_single_need(
        need, config, node["highlight"], needs_view.values()
    ):
        params.append(("color", "red"))
    elif node["border_color"]:
        color = match_variants(
            node["border_color"],
            {**need},
            config.variants,
            location=node,
        )
        if color:
            params.append(("color", _quote("#" + color)))

    id = _quote(need["id_complete"])
    param_str = ", ".join(f"{key}={value}" for key, value in params)
    return f"{id} [{param_str}];\n"


def _render_subgraph(
    need: NeedsInfoType,
    node: NeedflowGraphiz,
    needs_view: NeedsView,
    config: NeedsSphinxConfig,
    calc_link: Callable[[NeedsInfoType], str | None],
    id_comp_to_need: dict[str, NeedsInfoType],
    rendered_nodes: dict[str, _RenderedNode],
) -> str:
    """Render a subgraph in the graphviz format."""
    params: list[tuple[str, str]] = []

    # label
    params.append(("label", _label(need, "center")))
    params.append(("tooltip", _quote(need["id_complete"])))

    # link
    if _link := calc_link(need):
        params.extend([("href", _quote(_link)), ("target", _quote("_top"))])

    # shape
    if need["is_need"]:
        params.append(("shape", _quote(need["type_style"])))
    else:
        params.append(("shape", "rectangle"))

    # fill color
    params.append(("style", "filled"))
    if need["type_color"]:
        params.append(("fillcolor", _quote(need["type_color"])))

    # outline color
    if node["highlight"] and filter_single_need(need, config, node["highlight"]):
        params.append(("color", "red"))
    elif node["border_color"]:
        color = match_variants(
            node["border_color"],
            {**need},
            config.variants,
            location=node,
        )
        if color:
            params.append(("color", _quote("#" + color)))

    # we need to create an invisible node to allow links to the subgraph
    id = _quote(need["id_complete"])
    ghost_node = f'{id} [style=invis, width=0, height=0, label=""];'

    cluster_id = _quote("cluster_" + need["id_complete"])
    param_str = "\n".join(f"  {key}={value};" for key, value in params)

    rendered_nodes[need["id_complete"]] = {
        "need": need,
        "cluster_id": "cluster_" + need["id_complete"],
    }

    children = ""
    if need["is_need"] and need["parts"]:
        children += "  // parts:\n"
        for need_part_id in need["parts"]:
            need_part_id = need["id"] + "." + need_part_id
            if need_part_id in id_comp_to_need:
                children += textwrap.indent(
                    _render_node(
                        id_comp_to_need[need_part_id],
                        node,
                        needs_view,
                        config,
                        calc_link,
                        id_comp_to_need,
                        rendered_nodes,
                        False,
                    ),
                    "  ",
                )
    if need["parent_needs_back"]:
        children += "  // child needs:\n"
        for child_need_id in need["parent_needs_back"]:
            if child_need_id in id_comp_to_need:
                children += textwrap.indent(
                    _render_node(
                        id_comp_to_need[child_need_id],
                        node,
                        needs_view,
                        config,
                        calc_link,
                        id_comp_to_need,
                        rendered_nodes,
                    ),
                    "  ",
                )

    return f"subgraph {cluster_id} {{\n{param_str}\n\n  {ghost_node}\n{children}\n}};\n"


def _label(need: NeedsInfoType, align: Literal["left", "right", "center"]) -> str:
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
    need: NeedsInfoType,
    link: str,
    link_type: LinkOptionsType,
    node: NeedflowGraphiz,
    config: NeedsSphinxConfig,
    rendered_nodes: dict[str, _RenderedNode],
) -> str:
    """Render an edge in the graphviz format."""
    if need["id_complete"] not in rendered_nodes or link not in rendered_nodes:
        # if the start or end node is not rendered, we should not create a link
        return ""

    show_links = node["show_link_names"] or config.flow_show_links

    params: list[tuple[str, str]] = []

    if show_links:
        params.append(("label", _quote(link_type["outgoing"])))

    is_part = "." in link or "." in need["id_complete"]
    params.extend(
        _style_params_from_link_type(
            link_type.get("style_part", "dotted")
            if is_part
            else link_type.get("style", ""),
            link_type.get("style_start", "-"),
            link_type.get("style_end", "->"),
        )
    )

    start_id = _quote(need["id_complete"])
    if (ltail := rendered_nodes[need["id_complete"]]["cluster_id"]) is not None:
        # the need has been created as a subgraph and so we also need to create a logical link to the cluster
        params.append(("ltail", _quote(ltail)))

    end_id = _quote(link)
    if (lhead := rendered_nodes[link]["cluster_id"]) is not None:
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


def _create_legend(needs: list[NeedsInfoType], config: NeedsSphinxConfig) -> str:
    """Create a legend for the graph."""

    # TODO also show links in legend

    # filter types by ones that are actually used
    types = {need["type"] for need in needs}
    need_types = [ntype for ntype in config.types if ntype["directive"] in types]

    label = '<<TABLE border="0">'
    label += '\n<TR><TD align="center"><B>Legend</B></TD></TR>'

    for need_type in need_types:
        title = html.escape(need_type["title"])
        color = _quote(need_type["color"])
        label += f'\n<TR><TD align="left" bgcolor={color}>{title}</TD></TR>'

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
        alt = attrributes.get("alt", "needflow graphviz diagram")
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
