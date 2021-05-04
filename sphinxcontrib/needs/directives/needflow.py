import html
import os
import re
from typing import Iterable

from docutils import nodes
from docutils.parsers.rst import directives
from jinja2 import Template
from sphinxcontrib.plantuml import (
    generate_name,  # Need for plantuml filename calculation
)

from sphinxcontrib.needs.diagrams_common import calculate_link, create_legend
from sphinxcontrib.needs.filter_common import (
    FilterBase,
    filter_single_need,
    process_filters,
)
from sphinxcontrib.needs.logging import get_logger

logger = get_logger(__name__)


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

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, "need_all_needflows"):
            env.need_all_needflows = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, "needs_all_needs"):
            env.needs_all_needs = {}

        id = env.new_serialno("needflow")
        targetid = "needflow-{docname}-{id}".format(docname=env.docname, id=id)
        targetnode = nodes.target("", "", ids=[targetid])

        all_link_types = ",".join(x["option"] for x in env.config.needs_extra_links)
        link_types = list(split_link_types(self.options.get("link_types", all_link_types)))

        config_names = self.options.get("config", None)
        configs = []
        if config_names:
            for config_name in config_names.split(","):
                config_name = config_name.strip()
                if config_name and config_name in env.config.needs_flow_configs:
                    configs.append(env.config.needs_flow_configs[config_name])

        scale = self.options.get("scale", "100").replace("%", "")
        if not scale.isdigit():
            raise Exception('Needflow scale value must be a number. "{}" found'.format(scale))
        if int(scale) < 1 or int(scale) > 300:
            raise Exception('Needflow scale value must be between 1 and 300. "{}" found'.format(scale))

        highlight = self.options.get("highlight", "")

        caption = None
        if self.arguments:
            caption = self.arguments[0]

        # Add the need and all needed information
        env.need_all_needflows[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_node": targetnode,
            "caption": caption,
            "show_filters": "show_filters" in self.options,
            "show_legend": "show_legend" in self.options,
            "show_link_names": "show_link_names" in self.options,
            "debug": "debug" in self.options,
            "config_names": config_names,
            "config": "\n".join(configs),
            "scale": scale,
            "highlight": highlight,
            "align": self.options.get("align", None),
            "link_types": link_types,
            "env": env,
        }
        env.need_all_needflows[targetid].update(self.collect_filter_attributes())

        return [targetnode] + [Needflow("")]


def split_link_types(link_types: str) -> Iterable[str]:
    def is_valid(link_type) -> bool:
        if len(link_type) == 0 or link_type.isspace():
            logger.warning("Scruffy link_type definition found in needflow." "Defined link_type contains spaces only.")
            return False
        return True

    return filter(
        is_valid,
        (x.strip() for x in re.split(";|,", link_types)),
    )


def make_entity_name(name):
    """Creates a valid PlantUML entity name from the given value."""
    invalid_chars = "-=!#$%^&*[](){}/~'`<>:;"
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name


def process_needflow(app, doctree, fromdocname):
    # Replace all needflow nodes with a list of the collected needs.
    # Augment each need with a backlink to the original location.
    env = app.builder.env

    link_types = env.config.needs_extra_links
    allowed_link_types_options = [link.upper() for link in env.config.needs_flow_link_types]

    # NEEDFLOW
    for node in doctree.traverse(Needflow):
        if not app.config.needs_include_needs:
            # Ok, this is really dirty.
            # If we replace a node, docutils checks, if it will not lose any attributes.
            # But this is here the case, because we are using the attribute "ids" of a node.
            # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
            # before docutils claims about it.
            for att in ("ids", "names", "classes", "dupnames"):
                node[att] = []
            node.replace_self([])
            continue

        id = node.attributes["ids"][0]
        current_needflow = env.need_all_needflows[id]
        all_needs = env.needs_all_needs

        option_link_types = [link.upper() for link in current_needflow["link_types"]]
        for lt in option_link_types:
            if lt not in [link["option"].upper() for link in link_types]:
                logger.warning(
                    "Unknown link type {link_type} in needflow {flow}. Allowed values: {link_types}".format(
                        link_type=lt, flow=current_needflow["target_node"], link_types=",".join(link_types)
                    )
                )

        content = []
        try:
            if "sphinxcontrib.plantuml" not in app.config.extensions:
                raise ImportError
            from sphinxcontrib.plantuml import plantuml
        except ImportError:
            content = nodes.error()
            para = nodes.paragraph()
            text = nodes.Text("PlantUML is not available!", "PlantUML is not available!")
            para += text
            content.append(para)
            node.replace_self(content)
            continue

        plantuml_block_text = ".. plantuml::\n" "\n" "   @startuml" "   @enduml"
        puml_node = plantuml(plantuml_block_text, **dict())
        puml_node["uml"] = "@startuml\n"
        puml_connections = ""

        # Adding config
        config = current_needflow["config"]
        if config and len(config) >= 3:
            # Remove all empty lines
            config = "\n".join([line.strip() for line in config.split("\n") if line.strip()])
            puml_node["uml"] += "\n' Config\n\n"
            puml_node["uml"] += config
            puml_node["uml"] += "\n\n"

        all_needs = list(all_needs.values())
        found_needs = process_filters(all_needs, current_needflow)

        processed_need_part_ids = []

        puml_node["uml"] += "\n' Nodes definition \n\n"

        for need_info in found_needs:
            # Check if need_part was already handled during handling of parent need.
            # If this is the case, it is already part of puml-code and we do not need to create a node.
            if not (need_info["is_part"] and need_info["id_complete"] in processed_need_part_ids):
                # Check if we need to embed need_parts into parent need, because they are also part of search result.
                node_part_code = ""
                valid_need_parts = [x for x in found_needs if x["is_part"] and x["id_parent"] == need_info["id"]]
                for need_part in valid_need_parts:
                    part_link = calculate_link(app, need_part)
                    diagram_template = Template(env.config.needs_diagram_template)
                    part_text = diagram_template.render(**need_part)
                    part_colors = []
                    if need_part["type_color"]:
                        # We set # later, as the user may not have given a color and the node must get highlighted
                        part_colors.append(need_part["type_color"].replace("#", ""))

                    if current_needflow["highlight"] and filter_single_need(
                        need_part, current_needflow["highlight"], all_needs
                    ):
                        part_colors.append("line:FF0000")

                    node_part_code += '{style} "{node_text}" as {id} [[{link}]] #{color}\n'.format(
                        id=make_entity_name(need_part["id_complete"]),
                        node_text=part_text,
                        link=part_link,
                        color=";".join(part_colors),
                        style="rectangle",
                    )

                    processed_need_part_ids.append(need_part["id_complete"])

                link = calculate_link(app, need_info)

                diagram_template = Template(env.config.needs_diagram_template)
                node_text = diagram_template.render(**need_info)
                if need_info["is_part"]:
                    need_id = need_info["id_complete"]
                else:
                    need_id = need_info["id"]

                colors = []
                if need_info["type_color"]:
                    # We set # later, as the user may not have given a color and the node must get highlighted
                    colors.append(need_info["type_color"].replace("#", ""))

                if current_needflow["highlight"] and filter_single_need(
                    need_info, current_needflow["highlight"], all_needs
                ):
                    colors.append("line:FF0000")

                # Only add subelements and their {...} container, if we really need them.
                # Otherwise plantuml may not set style correctly, if {..} is empty
                if node_part_code:
                    node_part_code = "{{\n {} }}".format(node_part_code)

                style = need_info["type_style"]

                node_code = '{style} "{node_text}" as {id} [[{link}]] #{color} {need_parts}\n'.format(
                    id=make_entity_name(need_id),
                    node_text=node_text,
                    link=link,
                    color=";".join(colors),
                    style=style,
                    need_parts=node_part_code,
                )
                puml_node["uml"] += node_code

            for link_type in link_types:
                # Skip link-type handling, if it is not part of a specified list of allowed link_types or
                # if not part of the overall configuration of needs_flow_link_types
                if (current_needflow["link_types"] and link_type["option"].upper() not in option_link_types) or (
                    not current_needflow["link_types"] and link_type["option"].upper() not in allowed_link_types_options
                ):
                    continue

                for link in need_info[link_type["option"]]:
                    # If source or target of link is a need_part, a specific style is needed
                    if "." in link or "." in need_info["id_complete"]:
                        final_link = link
                        if current_needflow["show_link_names"] or env.config.needs_flow_show_links:
                            desc = link_type["outgoing"] + "\\n"
                            comment = ": {desc}".format(desc=desc)
                        else:
                            comment = ""

                        if "style_part" in link_type.keys() and link_type["style_part"]:
                            link_style = "[{style}]".format(style=link_type["style_part"])
                        else:
                            link_style = "[dotted]"
                    else:
                        final_link = link
                        if current_needflow["show_link_names"] or env.config.needs_flow_show_links:
                            comment = ": {desc}".format(desc=link_type["outgoing"])
                        else:
                            comment = ""

                        if "style" in link_type.keys() and link_type["style"]:
                            link_style = "[{style}]".format(style=link_type["style"])
                        else:
                            link_style = ""

                    # Do not create an links, if the link target is not part of the search result.
                    if final_link not in [x["id"] for x in found_needs if x["is_need"]] and final_link not in [
                        x["id_complete"] for x in found_needs if x["is_part"]
                    ]:
                        continue

                    if "style_start" in link_type.keys() and link_type["style_start"]:
                        style_start = link_type["style_start"]
                    else:
                        style_start = "-"

                    if "style_end" in link_type.keys() and link_type["style_end"]:
                        style_end = link_type["style_end"]
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

        puml_node["uml"] += "\n' Connection definition \n\n"
        puml_node["uml"] += puml_connections

        # Create a legend
        if current_needflow["show_legend"]:
            puml_node["uml"] += create_legend(app.config.needs_types)

        puml_node["uml"] += "\n@enduml"
        puml_node["incdir"] = os.path.dirname(current_needflow["docname"])
        puml_node["filename"] = os.path.split(current_needflow["docname"])[1]  # Needed for plantuml >= 0.9

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
            img_locaton = "../" * subfolder_amount + "_images/" + gen_flow_link[0].split("/")[-1]
            flow_ref = nodes.reference("t", current_needflow["caption"], refuri=img_locaton)
            puml_node += nodes.caption("", "", flow_ref)

        content.append(puml_node)

        if len(content) == 0:
            nothing_found = "No needs passed the filters"
            para = nodes.paragraph()
            nothing_found_node = nodes.Text(nothing_found, nothing_found)
            para += nothing_found_node
            content.append(para)
        if current_needflow["show_filters"]:
            para = nodes.paragraph()
            filter_text = "Used filter:"
            filter_text += (
                " status(%s)" % " OR ".join(current_needflow["status"]) if len(current_needflow["status"]) > 0 else ""
            )
            if len(current_needflow["status"]) > 0 and len(current_needflow["tags"]) > 0:
                filter_text += " AND "
            filter_text += (
                " tags(%s)" % " OR ".join(current_needflow["tags"]) if len(current_needflow["tags"]) > 0 else ""
            )
            if (len(current_needflow["status"]) > 0 or len(current_needflow["tags"]) > 0) and len(
                current_needflow["types"]
            ) > 0:
                filter_text += " AND "
            filter_text += (
                " types(%s)" % " OR ".join(current_needflow["types"]) if len(current_needflow["types"]) > 0 else ""
            )

            filter_node = nodes.emphasis(filter_text, filter_text)
            para += filter_node
            content.append(para)

        if current_needflow["debug"]:
            debug_container = nodes.container()
            if isinstance(puml_node, nodes.figure):
                data = puml_node.children[0]["uml"]
            else:
                data = puml_node["uml"]
            data = "\n".join([html.escape(line) for line in data.split("\n")])
            debug_para = nodes.raw("", "<pre>{}</pre>".format(data), format="html")
            debug_container += debug_para
            content += debug_container

        node.replace_self(content)
