from __future__ import annotations

import html
import textwrap
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Sequence,
    overload,
)

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.ext.graphviz import (
    ClickableMapDefinition,
    GraphvizError,
    align_spec,
    figure_wrapper,
    render_dot,
)
from sphinx.util.logging import getLogger

from sphinx_needs.config import LinkOptionsType, NeedsSphinxConfig
from sphinx_needs.data import NeedsFilteredBaseType, NeedsInfoType, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.diagrams_common import calculate_link
from sphinx_needs.directives.needflow import filter_by_tree, get_root_needs
from sphinx_needs.directives.utils import no_needs_found_paragraph
from sphinx_needs.filter_common import (
    FilterAttributesType,
    FilterBase,
    filter_single_need,
    process_filters,
)
from sphinx_needs.utils import (
    add_doc,
    match_variants,
    remove_node_from_tree,
    split_link_types,
)

try:
    from sphinx.writers.html5 import HTML5Translator
except ImportError:
    from sphinx.writers.html import HTML5Translator

LOGGER = getLogger(__name__)


class NeedGraph(nodes.General, nodes.Element):
    if TYPE_CHECKING:

        def __init__(
            self,
            rawsource: str,
            /,
            *,
            docname: str,
            target_id: str,
            resolved_content: str | None,
            alt: str,
            align: str,
            debug: bool,
            root_id: str | None,
            root_direction: str,
            root_depth: int | None,
            link_types: list[str],
            highlight: str,
            border_color: str | None,
            show_link_names: bool,
            config: str,
            **attributes: Any,
        ) -> None: ...

        @overload  # type: ignore[override]
        def __getitem__(self, index: Literal["docname"]) -> str: ...

        @overload
        def __getitem__(self, index: Literal["target_id"]) -> str: ...

        @overload
        def __getitem__(self, index: Literal["resolved_content"]) -> str | None: ...

        @overload
        def __getitem__(self, index: Literal["alt"]) -> str: ...

        @overload
        def __getitem__(self, index: Literal["align"]) -> str: ...

        @overload
        def __getitem__(self, index: Literal["debug"]) -> bool: ...

        @overload
        def __getitem__(self, index: Literal["root_id"]) -> str | None: ...

        @overload
        def __getitem__(self, index: Literal["config"]) -> str: ...

        @overload
        def __getitem__(
            self, index: Literal["root_direction"]
        ) -> Literal["both", "incoming", "outgoing"]: ...

        @overload
        def __getitem__(self, index: Literal["root_depth"]) -> int | None: ...

        @overload
        def __getitem__(self, index: Literal["link_types"]) -> list[str]: ...

        @overload
        def __getitem__(self, index: Literal["highlight"]) -> str: ...

        @overload
        def __getitem__(self, index: Literal["border_color"]) -> str | None: ...

        @overload
        def __getitem__(self, index: Literal["show_link_names"]) -> bool: ...

        def __getitem__(self, index: str) -> Any: ...

    def get_filter_attributes(self) -> NeedsFilteredBaseType:
        data: FilterAttributesType = {
            "status": self["status"],  # type: ignore[call-overload]
            "tags": self["tags"],  # type: ignore[call-overload]
            "types": self["types"],  # type: ignore[call-overload]
            "sort_by": self["sort_by"],  # type: ignore[call-overload]
            "filter": self["filter"],  # type: ignore[call-overload]
            "filter_code": self["filter_code"],  # type: ignore[call-overload]
            "filter_func": self["filter_func"],  # type: ignore[call-overload]
            "export_id": self["export_id"],  # type: ignore[call-overload]
            "filter_warning": self["filter_warning"],  # type: ignore[call-overload]
        }
        return {
            **data,
            "docname": self["docname"],
            "lineno": self.line or 0,
            "target_id": self["target_id"],
        }


class NeedGraphDirective(FilterBase):
    """
    Directive to create need flow charts using graphviz
    """

    optional_arguments = 1  # the caption
    final_argument_whitespace = True
    option_spec = {
        "alt": directives.unchanged,
        "align": align_spec,
        "class": directives.class_option,
        "name": directives.unchanged,
        "debug": directives.flag,
        # initial filter options
        "root_id": directives.unchanged_required,
        "root_direction": lambda c: directives.choice(
            c, ("both", "incoming", "outgoing")
        ),
        "root_depth": directives.nonnegative_int,
        # formatting
        "highlight": directives.unchanged_required,
        "border_color": directives.unchanged_required,
        "show_link_names": directives.flag,
        "config": directives.unchanged_required,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self) -> Sequence[nodes.Node]:
        LOGGER.warning(
            f"{self.name!r} is an experimental feature [needs.experimental]",
            location=self.get_location(),
            type="needs",
            subtype="experimental",
        )

        add_doc(self.env, self.env.docname)

        id = self.env.new_serialno("needgraph")
        targetid = f"needgraph-{self.env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        needs_config = NeedsSphinxConfig(self.env.config)
        all_link_types = ",".join(x["option"] for x in needs_config.extra_links)
        link_types = split_link_types(
            self.options.get("link_types", all_link_types),
            (self.env.docname, self.lineno),
        )

        configs = []
        if config_names := self.options.get("config"):
            for config_name in config_names.split(","):
                config_name = config_name.strip()
                if config_name and config_name in needs_config.graph_configs:
                    configs.append(needs_config.graph_configs[config_name])

        node = NeedGraph(
            "",
            docname=self.env.docname,
            target_id=targetid,
            resolved_content=None,
            alt=self.options.get("alt", "needgraph"),
            align=self.options.get("align", "center"),
            debug="debug" in self.options,
            link_types=link_types,
            root_id=self.options.get("root_id"),
            root_direction=self.options.get("root_direction", "all"),
            root_depth=self.options.get("root_depth", None),
            highlight=self.options.get("highlight", ""),
            border_color=self.options.get("border_color", None),
            show_link_names="show_link_names" in self.options,
            config="\n".join(configs),
            **self.collect_filter_attributes(),
        )
        self.set_source_info(node)
        if "class" in self.options:
            node["classes"] = self.options["class"]

        if not self.arguments:
            self.add_name(node)
            return [targetnode, node]
        else:
            figure = figure_wrapper(self, node, self.arguments[0])  # type: ignore[arg-type]
            self.add_name(figure)
            return [targetnode, figure]


@measure_time("needgraph")
def process_needgraph(
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

    node: NeedGraph
    for node in found_nodes:  # type: ignore[assignment]
        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        if app.builder.format != "html":
            LOGGER.warning(
                "NeedGraph is only supported for HTML output. [needs.needgraph]",
                location=node,
                type="needs",
                subtype="needgraph",
            )
            remove_node_from_tree(node)
            continue

        option_link_types = [link.upper() for link in node["link_types"]]
        for lt in option_link_types:
            if lt not in link_type_names:
                LOGGER.warning(
                    "Unknown link type {link_type} in needflow {flow}. Allowed values: {link_types} [needs.needgraph]".format(
                        link_type=lt,
                        flow=node["target_id"],
                        link_types=",".join(link_type_names),
                    ),
                    type="needs",
                    subtype="needgraph",
                )

        # compute the allowed link names
        allowed_link_types: list[LinkOptionsType] = []
        for link_type in needs_config.extra_links:
            # Skip link-type handling, if it is not part of a specified list of allowed link_types or
            # if not part of the overall configuration of needs_flow_link_types
            if (
                node["link_types"]
                and link_type["option"].upper() not in option_link_types
            ) or (
                not node["link_types"]
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
                node["root_direction"],
                node["root_depth"],
            ).values()
            if (root_id := node["root_id"])
            else all_needs.values()
        )
        filtered_needs = process_filters(
            app, init_filtered_needs, node.get_filter_attributes()
        )

        # TODO show_filters option

        if not filtered_needs:
            node.replace_self(no_needs_found_paragraph(node.get("filter_warning")))

        content = "digraph needgraph {\n\n"

        # global settings
        content += node["config"] + "\n\n"

        # calculate node definitions
        content += "// node definitions\n"
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

        # TODO show_legend

        content += "}"

        node["resolved_content"] = content

        if node["debug"]:
            code = nodes.literal_block(
                content, content, language="dot", linenos=True, force=True
            )
            code.source, code.line = code.source, node.line
            if node.parent is not None and isinstance(node.parent, nodes.figure):
                node.parent.parent.insert(
                    node.parent.parent.index(node.parent) + 1, code
                )
            else:
                node.replace_self([node, code])


def _quote(text: str) -> str:
    """Quote a string for use in a graphviz file."""
    return '"' + text.replace('"', '\\"') + '"'


def _render_node(
    need: NeedsInfoType, node: NeedGraph, config: NeedsSphinxConfig, link: str
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
            location=(node["docname"], node.line),
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
    node: NeedGraph,
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


def html_visit_needgraph(self: HTML5Translator, node: NeedGraph) -> None:
    """This visitor closely mimics ``sphinx.ext.graphviz.html_visit_graphviz``,
    however, that is not used directly due to these current key differences:

    - The warning is changed, to give the location of the source directive
    - svg's are output as ``<img>`` tags, not ``<object>`` tags (allows e.g. for transparency)
    - svg's are wrapped in an `<a>` tag, to allow for linking to the svg file
    """
    code = node["resolved_content"]
    if code is None:
        LOGGER.warning(
            "Content has not been resolved [needs.needgraph]",
            location=node,
            type="needs",
            subtype="needgraph",
        )
        raise nodes.SkipNode
    format = self.builder.config.graphviz_output_format
    if format not in ("png", "svg"):
        LOGGER.warning(
            f"graphviz_output_format must be one of 'png', 'svg', but is {format!r} [needs.needgraph]",
            location=node,
            type="needs",
            subtype="needgraph",
        )
        raise nodes.SkipNode
    try:
        fname, outfn = render_dot(
            self, code, {"docname": node["docname"]}, format, "needgraph"
        )
    except GraphvizError as exc:
        LOGGER.warning(
            f"graphviz code failed to render (run with :debug: to see code): {exc} [needs.needgraph]",
            location=node,
            type="needs",
            subtype="needgraph",
        )
        raise nodes.SkipNode from exc

    classes = ["graphviz", *node.get("classes", [])]
    imgcls = " ".join(filter(None, classes))

    if fname is None:
        self.body.append(self.encode(code))
    else:
        alt = node.get("alt", "graphviz diagram")
        if "align" in node:
            self.body.append(
                f'<div align="{node["align"]}" class="align-{node["align"]}">'
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
        if "align" in node:
            self.body.append("</div>\n")

    raise nodes.SkipNode
