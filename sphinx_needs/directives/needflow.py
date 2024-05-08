from __future__ import annotations

import html
import os
from typing import Iterable, Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from jinja2 import Template
from sphinx.application import Sphinx
from sphinxcontrib.plantuml import (
    generate_name,  # Need for plantuml filename calculation
)

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import (
    NeedsFlowType,
    NeedsInfoType,
    SphinxNeedsData,
)
from sphinx_needs.debug import measure_time
from sphinx_needs.diagrams_common import calculate_link, create_legend
from sphinx_needs.directives.utils import no_needs_found_paragraph
from sphinx_needs.filter_common import FilterBase, filter_single_need, process_filters
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import (
    add_doc,
    get_scale,
    remove_node_from_tree,
    split_link_types,
)

logger = get_logger(__name__)


NEEDFLOW_TEMPLATES: dict[str, Template] = {}


class Needflow(nodes.General, nodes.Element):
    pass


class NeedflowDirective(FilterBase):
    """
    Directive to get flow charts.
    """

    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        "show_legend": directives.flag,
        "show_filters": directives.flag,
        "show_link_names": directives.flag,
        "link_types": directives.unchanged_required,
        "config": directives.unchanged_required,
        "scale": directives.unchanged_required,
        "highlight": directives.unchanged_required,
        "align": directives.unchanged_required,
        "debug": directives.flag,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    @measure_time("needflow")
    def run(self) -> Sequence[nodes.Node]:
        env = self.env
        needs_config = NeedsSphinxConfig(env.config)
        location = (env.docname, self.lineno)

        id = env.new_serialno("needflow")
        targetid = f"needflow-{env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        all_link_types = ",".join(x["option"] for x in needs_config.extra_links)
        link_types = split_link_types(
            self.options.get("link_types", all_link_types), location
        )

        config_names = self.options.get("config")
        configs = []
        if config_names:
            for config_name in config_names.split(","):
                config_name = config_name.strip()
                if config_name and config_name in needs_config.flow_configs:
                    configs.append(needs_config.flow_configs[config_name])

        # Add the need and all needed information
        data = SphinxNeedsData(env).get_or_create_flows()
        data[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            # note these are the same as DiagramBase.collect_diagram_attributes
            "show_legend": "show_legend" in self.options,
            "show_filters": "show_filters" in self.options,
            "show_link_names": "show_link_names" in self.options,
            "link_types": link_types,
            "config": "\n".join(configs),
            "config_names": config_names,
            "scale": get_scale(self.options, location),
            "highlight": self.options.get("highlight", ""),
            "align": self.options.get("align"),
            "debug": "debug" in self.options,
            "caption": self.arguments[0] if self.arguments else None,
            **self.collect_filter_attributes(),
        }

        add_doc(env, env.docname)

        return [targetnode, Needflow("")]


def make_entity_name(name: str) -> str:
    """Creates a valid PlantUML entity name from the given value."""
    invalid_chars = "-=!#$%^&*[](){}/~'`<>:;"
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name


def get_need_node_rep_for_plantuml(
    app: Sphinx,
    fromdocname: str,
    current_needflow: NeedsFlowType,
    all_needs: Iterable[NeedsInfoType],
    need_info: NeedsInfoType,
) -> str:
    """Calculate need node representation for plantuml."""
    needs_config = NeedsSphinxConfig(app.config)
    diagram_template = get_template(needs_config.diagram_template)

    node_text = diagram_template.render(**need_info, **needs_config.render_context)

    node_link = calculate_link(app, need_info, fromdocname)

    node_colors = []
    if need_info["type_color"]:
        # We set # later, as the user may not have given a color and the node must get highlighted
        node_colors.append(need_info["type_color"].replace("#", ""))

    if current_needflow["highlight"] and filter_single_need(
        need_info, needs_config, current_needflow["highlight"], all_needs
    ):
        node_colors.append("line:FF0000")

    # need parts style use default "rectangle"
    if need_info["is_need"]:
        node_style = need_info["type_style"]
    else:
        node_style = "rectangle"

    # node representation for plantuml
    need_node_code = '{style} "{node_text}" as {id} [[{link}]] #{color}'.format(
        id=make_entity_name(need_info["id_complete"]),
        node_text=node_text,
        link=node_link,
        color=";".join(node_colors),
        style=node_style,
    )
    return need_node_code


def walk_curr_need_tree(
    app: Sphinx,
    fromdocname: str,
    current_needflow: NeedsFlowType,
    all_needs: Iterable[NeedsInfoType],
    found_needs: list[NeedsInfoType],
    need: NeedsInfoType,
) -> str:
    """
    Walk through each need to find all its child needs and need parts recursively and wrap them together in nested structure.
    """

    curr_need_tree = ""

    if not need["parts"] and not need["parent_needs_back"]:
        return curr_need_tree

    # We do have embedded needs or need parts, so we will add a open "{"
    curr_need_tree += "{\n"

    if need["is_need"] and need["parts"]:
        # add comment for easy debugging
        curr_need_tree += "'parts:\n"
        for need_part_id in need["parts"].keys():
            # cal need part node
            need_part_id = need["id"] + "." + need_part_id
            # get need part from need part id
            for found_need in found_needs:
                if need_part_id == found_need["id_complete"]:
                    need_part = found_need
                    # get need part node
                    need_part_node = get_need_node_rep_for_plantuml(
                        app, fromdocname, current_needflow, all_needs, need_part
                    )
                    curr_need_tree += need_part_node + "\n"

    # check if curr need has children
    if need["parent_needs_back"]:
        # add comment for easy debugging
        curr_need_tree += "'child needs:\n"

        # walk throgh all child needs one by one
        child_needs_ids = need["parent_needs_back"]

        idx = 0
        while idx < len(child_needs_ids):
            # start from one child
            curr_child_need_id = child_needs_ids[idx]
            # get need from id
            for need in found_needs:
                if need["id_complete"] == curr_child_need_id:
                    curr_child_need = need
                    # get child need node
                    child_need_node = get_need_node_rep_for_plantuml(
                        app, fromdocname, current_needflow, all_needs, curr_child_need
                    )
                    curr_need_tree += child_need_node
                    # check curr need child has children or has parts
                    if curr_child_need["parent_needs_back"] or curr_child_need["parts"]:
                        curr_need_tree += walk_curr_need_tree(
                            app,
                            fromdocname,
                            current_needflow,
                            all_needs,
                            found_needs,
                            curr_child_need,
                        )
                    # add newline for next element
                    curr_need_tree += "\n"
            idx += 1

    # We processed embedded needs or need parts, so we will close with "}"
    curr_need_tree += "}"

    return curr_need_tree


def get_root_needs(found_needs: list[NeedsInfoType]) -> list[NeedsInfoType]:
    return_list = []
    for current_need in found_needs:
        if current_need["is_need"]:
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


def cal_needs_node(
    app: Sphinx,
    fromdocname: str,
    current_needflow: NeedsFlowType,
    all_needs: Iterable[NeedsInfoType],
    found_needs: list[NeedsInfoType],
) -> str:
    """Calculate and get needs node representaion for plantuml including all child needs and need parts."""
    top_needs = get_root_needs(found_needs)
    curr_need_tree = ""
    for top_need in top_needs:
        top_need_node = get_need_node_rep_for_plantuml(
            app, fromdocname, current_needflow, all_needs, top_need
        )
        curr_need_tree += (
            top_need_node
            + walk_curr_need_tree(
                app,
                fromdocname,
                current_needflow,
                all_needs,
                found_needs,
                top_need,
            )
            + "\n"
        )
    return curr_need_tree


@measure_time("needflow")
def process_needflow(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    # Replace all needflow nodes with a list of the collected needs.
    # Augment each need with a backlink to the original location.
    env = app.env
    needs_config = NeedsSphinxConfig(app.config)
    env_data = SphinxNeedsData(env)
    all_needs = env_data.get_or_create_needs()

    link_types = needs_config.extra_links
    link_type_names = [link["option"].upper() for link in link_types]
    allowed_link_types_options = [link.upper() for link in needs_config.flow_link_types]

    # NEEDFLOW
    # for node in doctree.findall(Needflow):
    for node in found_nodes:
        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        id = node.attributes["ids"][0]
        current_needflow = env_data.get_or_create_flows()[id]

        option_link_types = [link.upper() for link in current_needflow["link_types"]]
        for lt in option_link_types:
            if lt not in link_type_names:
                logger.warning(
                    "Unknown link type {link_type} in needflow {flow}. Allowed values: {link_types} [needs]".format(
                        link_type=lt,
                        flow=current_needflow["target_id"],
                        link_types=",".join(link_type_names),
                    ),
                    type="needs",
                )

        try:
            if "sphinxcontrib.plantuml" not in app.config.extensions:
                raise ImportError
            from sphinxcontrib.plantuml import plantuml
        except ImportError:
            error_node = nodes.error()
            para = nodes.paragraph()
            text = nodes.Text("PlantUML is not available!")
            para += text
            error_node.append(para)
            node.replace_self(error_node)
            continue

        content: list[nodes.Element] = []

        found_needs = process_filters(app, all_needs.values(), current_needflow)

        if found_needs:
            plantuml_block_text = ".. plantuml::\n" "\n" "   @startuml" "   @enduml"
            puml_node = plantuml(plantuml_block_text)

            # Add source origin
            puml_node.line = current_needflow["lineno"]
            puml_node.source = env.doc2path(current_needflow["docname"])

            puml_node["uml"] = "@startuml\n"
            puml_connections = ""

            # Adding config
            config = current_needflow["config"]
            if config and len(config) >= 3:
                # Remove all empty lines
                config = "\n".join(
                    [line.strip() for line in config.split("\n") if line.strip()]
                )
                puml_node["uml"] += "\n' Config\n\n"
                puml_node["uml"] += config
                puml_node["uml"] += "\n\n"

            puml_node["uml"] += "\n' Nodes definition \n\n"

            for need_info in found_needs:
                for link_type in link_types:
                    # Skip link-type handling, if it is not part of a specified list of allowed link_types or
                    # if not part of the overall configuration of needs_flow_link_types
                    if (
                        current_needflow["link_types"]
                        and link_type["option"].upper() not in option_link_types
                    ) or (
                        not current_needflow["link_types"]
                        and link_type["option"].upper()
                        not in allowed_link_types_options
                    ):
                        continue

                    # skip creating links from child needs to their own parent need
                    if link_type["option"] == "parent_needs":
                        continue

                    for link in need_info[link_type["option"]]:  # type: ignore[literal-required]
                        # If source or target of link is a need_part, a specific style is needed
                        if "." in link or "." in need_info["id_complete"]:
                            final_link = link
                            if (
                                current_needflow["show_link_names"]
                                or needs_config.flow_show_links
                            ):
                                desc = link_type["outgoing"] + "\\n"
                                comment = f": {desc}"
                            else:
                                comment = ""

                            if _style_part := link_type.get("style_part"):
                                link_style = f"[{_style_part}]"
                            else:
                                link_style = "[dotted]"
                        else:
                            final_link = link
                            if (
                                current_needflow["show_link_names"]
                                or needs_config.flow_show_links
                            ):
                                comment = ": {desc}".format(desc=link_type["outgoing"])
                            else:
                                comment = ""

                            if _style := link_type.get("style"):
                                link_style = f"[{_style}]"
                            else:
                                link_style = ""

                        # Do not create an links, if the link target is not part of the search result.
                        if final_link not in [
                            x["id"] for x in found_needs if x["is_need"]
                        ] and final_link not in [
                            x["id_complete"] for x in found_needs if x["is_part"]
                        ]:
                            continue

                        if _style_start := link_type.get("style_start"):
                            style_start = _style_start
                        else:
                            style_start = "-"

                        if _style_end := link_type.get("style_end"):
                            style_end = _style_end
                        else:
                            style_end = "->"

                        puml_connections += "{id} {style_start}{link_style}{style_end} {link}{comment}\n".format(
                            id=make_entity_name(need_info["id_complete"]),
                            link=make_entity_name(final_link),
                            comment=comment,
                            link_style=link_style,
                            style_start=style_start,
                            style_end=style_end,
                        )

            # calculate needs node representation for plantuml
            puml_node["uml"] += cal_needs_node(
                app, fromdocname, current_needflow, all_needs.values(), found_needs
            )

            puml_node["uml"] += "\n' Connection definition \n\n"
            puml_node["uml"] += puml_connections

            # Create a legend
            if current_needflow["show_legend"]:
                puml_node["uml"] += create_legend(needs_config.types)

            puml_node["uml"] += "\n@enduml"
            puml_node["incdir"] = os.path.dirname(current_needflow["docname"])
            puml_node["filename"] = os.path.split(current_needflow["docname"])[
                1
            ]  # Needed for plantuml >= 0.9

            scale = int(current_needflow["scale"])
            # if scale != 100:
            puml_node["scale"] = scale

            puml_node = nodes.figure("", puml_node)

            if current_needflow["align"]:
                puml_node["align"] = current_needflow["align"]
            else:
                puml_node["align"] = "center"

            if current_needflow["caption"]:
                # Make the caption to a link to the original file.
                try:
                    if "SVG" in app.config.plantuml_output_format.upper():
                        file_ext = "svg"
                    else:
                        file_ext = "png"
                except Exception:
                    file_ext = "png"

                gen_flow_link = generate_name(app, puml_node.children[0], file_ext)
                current_file_parts = fromdocname.split("/")
                subfolder_amount = len(current_file_parts) - 1
                img_locaton = (
                    "../" * subfolder_amount
                    + "_images/"
                    + gen_flow_link[0].split("/")[-1]
                )
                flow_ref = nodes.reference(
                    "t", current_needflow["caption"], refuri=img_locaton
                )
                puml_node += nodes.caption("", "", flow_ref)

            # Add lineno to node
            puml_node.line = current_needflow["lineno"]

            content.append(puml_node)
        else:  # no needs found
            content.append(
                no_needs_found_paragraph(current_needflow.get("filter_warning"))
            )

        if current_needflow["show_filters"]:
            para = nodes.paragraph()
            filter_text = "Used filter:"
            filter_text += (
                " status({})".format(" OR ".join(current_needflow["status"]))
                if len(current_needflow["status"]) > 0
                else ""
            )
            if (
                len(current_needflow["status"]) > 0
                and len(current_needflow["tags"]) > 0
            ):
                filter_text += " AND "
            filter_text += (
                " tags({})".format(" OR ".join(current_needflow["tags"]))
                if len(current_needflow["tags"]) > 0
                else ""
            )
            if (
                len(current_needflow["status"]) > 0 or len(current_needflow["tags"]) > 0
            ) and len(current_needflow["types"]) > 0:
                filter_text += " AND "
            filter_text += (
                " types({})".format(" OR ".join(current_needflow["types"]))
                if len(current_needflow["types"]) > 0
                else ""
            )

            filter_node = nodes.emphasis(filter_text, filter_text)
            para += filter_node
            content.append(para)

        # We have to restrustructer the needflow
        # If this block should be organized differently
        if current_needflow["debug"] and found_needs:
            # We can only access puml_node if found_needs is set.
            # Otherwise it was not been set, or we get outdated data
            debug_container = nodes.container()
            if isinstance(puml_node, nodes.figure):
                data = puml_node.children[0]["uml"]  # type: ignore
            else:
                data = puml_node["uml"]
            data = "\n".join([html.escape(line) for line in data.split("\n")])
            debug_para = nodes.raw("", f"<pre>{data}</pre>", format="html")
            debug_container += debug_para
            content.append(debug_container)

        node.replace_self(content)


def get_template(template_name: str) -> Template:
    """Checks if a template got already rendered, if it's the case, return it"""

    if template_name not in NEEDFLOW_TEMPLATES:
        NEEDFLOW_TEMPLATES[template_name] = Template(template_name)

    return NEEDFLOW_TEMPLATES[template_name]
