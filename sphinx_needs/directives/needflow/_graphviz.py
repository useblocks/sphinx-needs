from __future__ import annotations

import html
import textwrap

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
from sphinx_needs.diagrams_common import calculate_link
from sphinx_needs.directives.needflow._directive import NeedflowGraphiz
from sphinx_needs.directives.utils import no_needs_found_paragraph
from sphinx_needs.filter_common import (
    filter_single_need,
    process_filters,
)
from sphinx_needs.utils import (
    match_variants,
    remove_node_from_tree,
)

from ._shared import create_filter_paragraph, filter_by_tree, get_root_needs

try:
    from sphinx.writers.html5 import HTML5Translator
except ImportError:
    from sphinx.writers.html import HTML5Translator

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
    all_needs = env_data.get_or_create_needs()

    link_type_names = [link["option"].upper() for link in needs_config.extra_links]
    allowed_link_types_options = [link.upper() for link in needs_config.flow_link_types]

    node: NeedflowGraphiz
    for node in found_nodes:  # type: ignore[assignment]
        attributes = node.attributes

        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        if app.builder.format != "html":
            LOGGER.warning(
                "NeedflowGraphiz is only supported for HTML output. [needs.needflow]",
                location=node,
                type="needs",
                subtype="needflow",
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
                LOGGER.warning(
                    "Unknown link type {link_type} in needflow {flow}. Allowed values: {link_types} [needs.needflow]".format(
                        link_type=lt,
                        flow=attributes["target_id"],
                        link_types=",".join(link_type_names),
                    ),
                    type="needs",
                    subtype="needflow",
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
                all_needs,
                root_id,
                allowed_link_types,
                attributes["root_direction"],
                attributes["root_depth"],
            ).values()
            if (root_id := attributes["root_id"])
            else all_needs.values()
        )
        filtered_needs = process_filters(app, init_filtered_needs, node.attributes)

        if not filtered_needs:
            node.replace_self(
                no_needs_found_paragraph(attributes.get("filter_warning"))
            )
            continue

        content = "digraph needflow {\ncompound=true;\n"

        # global settings
        for key, value in attributes["graphviz_style"].get("root", {}).items():
            content += f"{key}={_quote(str(value))};\n"
        for etype in ("graph", "node", "edge"):
            if etype in attributes["graphviz_style"]:
                content += f"{etype} [\n"
                for key, value in attributes["graphviz_style"][etype].items():  # type: ignore[literal-required]
                    content += f"  {key}={_quote(str(value))};\n"
                content += "]\n"

        # calculate node definitions
        content += "\n// node definitions\n"
        for root_need in get_root_needs(filtered_needs):
            # TODO handle child needs
            node_link = calculate_link(app, root_need, fromdocname, relative=".")
            content += _render_node(root_need, node, needs_config, node_link) + "\n"

        # calculate edge definitions
        content += "// edge definitions\n"
        for need in filtered_needs:
            for link_type in allowed_link_types:
                for link in need[link_type["option"]]:  # type: ignore[literal-required]
                    # Do not create links, if the link target is not part of the search result.
                    if link not in [
                        x["id"] for x in filtered_needs if x["is_need"]
                    ] and link not in [
                        x["id_complete"] for x in filtered_needs if x["is_part"]
                    ]:
                        continue
                    content += (
                        _render_edge(need, link, link_type, node, needs_config) + "\n"
                    )

        if attributes["show_legend"]:
            # TODO implement show_legend
            LOGGER.warning(
                "show_legend for the graphviz engine is not yet implemented [needs.needflow]",
                type="needs",
                subtype="needflow",
                location=node,
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


def _quote(text: str) -> str:
    """Quote a string for use in a graphviz file."""
    return '"' + text.replace('"', '\\"') + '"'


def _render_node(
    need: NeedsInfoType, node: NeedflowGraphiz, config: NeedsSphinxConfig, link: str
) -> str:
    """Render a node in the graphviz format."""
    params: list[tuple[str, str]] = []

    # label
    br = '<br align="left"/>'
    # note this text wrapping mimics the jinja wordwrap filter
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
        for line in need["title"].splitlines()
    )
    name = html.escape(need["type_name"])
    if need["is_need"]:
        _id = html.escape(need["id"])
    else:
        _id = f"{html.escape(need['id_parent'])}.<b>{html.escape(need['id'])}</b>"
    font_10 = '<font point-size="10">'
    font_12 = '<font point-size="12">'
    params.append(
        (
            "label",
            f"<{font_12}{name}</font>{br}<b>{title}</b>{br}{font_10}{_id}</font>{br}>",
        )
    )

    # link
    if link:
        params.append(("href", _quote(link)))

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

    id = _quote(need["id_complete"])
    param_str = ", ".join(f"{key}={value}" for key, value in params)
    return f"{id} [{param_str}];\n"


def _render_edge(
    need: NeedsInfoType,
    link: str,
    link_type: LinkOptionsType,
    node: NeedflowGraphiz,
    config: NeedsSphinxConfig,
) -> str:
    """Render an edge in the graphviz format."""
    show_links = node["show_link_names"] or config.flow_show_links

    label = _quote(link_type["outgoing"]) if show_links else '""'

    # If source or target of link is a need_part, a specific style is needed
    # TODO custom for styles for edges (mapping from plantuml to graphviz)
    if "." in link or "." in need["id_complete"]:
        link_style = "dotted"
        # if _style_part := link_type.get("style_part"):
        #     link_style = f"[{_style_part}]"
        # else:
        #     link_style = "[dotted]"
    else:
        link_style = "solid"
        # if _style := link_type.get("style"):
        #     link_style = f"[{_style}]"
        # else:
        #     link_style = ""

    # TODO custom for styles for edges (mapping from plantuml to graphviz)
    # if _style_start := link_type.get("style_start"):
    #     style_start = _style_start
    # else:
    #     style_start = "-"

    # if _style_end := link_type.get("style_end"):
    #     style_end = _style_end
    # else:
    #     style_end = "->"

    start_id = _quote(need["id_complete"])
    end_id = _quote(link)
    return f"{start_id} -> {end_id} [style={link_style}, label={label}];"


def html_visit_needflow_graphviz(self: HTML5Translator, node: NeedflowGraphiz) -> None:
    """This visitor closely mimics ``sphinx.ext.graphviz.html_visit_graphviz``,
    however, that is not used directly due to these current key differences:

    - The warning is changed, to give the location of the source directive
    - svg's are output as ``<img>`` tags, not ``<object>`` tags (allows e.g. for transparency)
    - svg's are wrapped in an `<a>` tag, to allow for linking to the svg file
    """
    code = node.get("resolved_content")
    if code is None:
        LOGGER.warning(
            "Content has not been resolved [needs.needflow]",
            location=node,
            type="needs",
            subtype="needflow",
        )
        raise nodes.SkipNode
    attrributes = node.attributes
    format = self.builder.config.graphviz_output_format
    if format not in ("png", "svg"):
        LOGGER.warning(
            f"graphviz_output_format must be one of 'png', 'svg', but is {format!r} [needs.needflow]",
            location=node,
            type="needs",
            subtype="needflow",
        )
        raise nodes.SkipNode
    try:
        fname, outfn = render_dot(
            self, code, {"docname": attrributes["docname"]}, format, "needflow"
        )
    except GraphvizError as exc:
        LOGGER.warning(
            f"graphviz code failed to render (run with :debug: to see code): {exc} [needs.needflow]",
            location=node,
            type="needs",
            subtype="needflow",
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
