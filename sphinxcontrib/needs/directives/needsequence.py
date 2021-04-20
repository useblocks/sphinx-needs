import os
import re

from docutils import nodes
from docutils.parsers.rst import directives
from sphinxcontrib.plantuml import (
    generate_name,  # Need for plantuml filename calculation
)

from sphinxcontrib.needs.diagrams_common import (
    DiagramBase,
    add_config,
    create_legend,
    get_debug_container,
    get_filter_para,
    no_plantuml,
)
from sphinxcontrib.needs.filter_common import FilterBase
from sphinxcontrib.needs.logging import get_logger

logger = get_logger(__name__)


class Needsequence(nodes.General, nodes.Element):
    pass


class NeedsequenceDirective(FilterBase, DiagramBase, Exception):
    """
    Directive to get sequence diagrams.
    """

    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        "start": directives.unchanged,
        "link_types": directives.unchanged,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)
    option_spec.update(DiagramBase.base_option_spec)

    def run(self):
        env = self.state.document.settings.env
        # Creates env.need_all_needsequences safely and other vars
        self.prepare_env("needsequences")

        id, targetid, targetnode = self.create_target("needsequence")

        start = self.options.get("start", None)
        if start is None or len(start.strip()) == 0:
            raise NeedSequenceException(
                "No valid start option given for needsequence. " "See file {}:{}".format(env.docname, self.lineno)
            )

        # Add the needsequence and all needed information
        env.need_all_needsequences[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_node": targetnode,
            "env": env,
            "start": self.options.get("start", ""),
        }
        # Data for filtering
        env.need_all_needsequences[targetid].update(self.collect_filter_attributes())
        # Data for diagrams
        env.need_all_needsequences[targetid].update(self.collect_diagram_attributes())

        return [targetnode] + [Needsequence("")]


def process_needsequence(app, doctree, fromdocname):
    # Replace all needsequence nodes with a list of the collected needs.
    env = app.builder.env

    link_types = env.config.needs_extra_links
    # allowed_link_types_options = [link.upper() for link in env.config.needs_flow_link_types]

    # NEEDSEQUENCE
    for node in doctree.traverse(Needsequence):
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
        current_needsequence = env.need_all_needsequences[id]
        all_needs_dict = env.needs_all_needs

        option_link_types = [link.upper() for link in current_needsequence["link_types"]]
        for lt in option_link_types:
            if lt not in [link["option"].upper() for link in link_types]:
                logger.warning(
                    "Unknown link type {link_type} in needsequence {flow}. Allowed values:"
                    " {link_types}".format(
                        link_type=lt, flow=current_needsequence["target_node"], link_types=",".join(link_types)
                    )
                )

        content = []
        try:
            if "sphinxcontrib.plantuml" not in app.config.extensions:
                raise ImportError
            from sphinxcontrib.plantuml import plantuml
        except ImportError:
            no_plantuml(node)
            continue

        plantuml_block_text = ".. plantuml::\n" "\n" "   @startuml" "   @enduml"
        puml_node = plantuml(plantuml_block_text, **dict())
        puml_node["uml"] = "@startuml\n"

        # Adding config
        config = current_needsequence["config"]
        puml_node["uml"] += add_config(config)

        # all_needs = list(all_needs_dict.values())

        start_needs_id = [x.strip() for x in re.split(";|,", current_needsequence["start"])]
        if len(start_needs_id) == 0:
            raise NeedsequenceDirective(
                "No start-id set for needsequence"
                " File {}"
                ":{}".format({current_needsequence["docname"]}, current_needsequence["lineno"])
            )

        puml_node["uml"] += "\n' Nodes definition \n\n"

        # Add  start participants
        p_string = ""
        c_string = ""
        for need_id in start_needs_id:
            try:
                need = all_needs_dict[need_id.strip()]
            except KeyError:
                raise NeedSequenceException(
                    "Given {} in needsequence unknown."
                    " File {}"
                    ":{}".format(need_id, current_needsequence["docname"], current_needsequence["lineno"])
                )

            # Add children of participants
            _msg_receiver_needs, p_string_new, c_string_new = get_message_needs(
                need, current_needsequence["link_types"], all_needs_dict, filter=current_needsequence["filter"]
            )
            p_string += p_string_new
            c_string += c_string_new

        puml_node["uml"] += p_string

        puml_node["uml"] += "\n' Connection definition \n\n"
        puml_node["uml"] += c_string

        # Create a legend
        if current_needsequence["show_legend"]:
            puml_node["uml"] += create_legend(app.config.needs_types)

        puml_node["uml"] += "\n@enduml"
        puml_node["incdir"] = os.path.dirname(current_needsequence["docname"])
        puml_node["filename"] = os.path.split(current_needsequence["docname"])[1]  # Needed for plantuml >= 0.9

        scale = int(current_needsequence["scale"])
        # if scale != 100:
        puml_node["scale"] = scale

        puml_node = nodes.figure("", puml_node)

        if current_needsequence["align"]:
            puml_node["align"] = current_needsequence["align"]
        else:
            puml_node["align"] = "center"

        if current_needsequence["caption"]:
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
            flow_ref = nodes.reference("t", current_needsequence["caption"], refuri=img_locaton)
            puml_node += nodes.caption("", "", flow_ref)

        content.append(puml_node)

        if len(content) == 0:
            nothing_found = "No needs passed the filters"
            para = nodes.paragraph()
            nothing_found_node = nodes.Text(nothing_found, nothing_found)
            para += nothing_found_node
            content.append(para)
        if current_needsequence["show_filters"]:
            content.append(get_filter_para(current_needsequence))

        if current_needsequence["debug"]:
            content += get_debug_container(puml_node)

        node.replace_self(content)


def get_message_needs(sender, link_types, all_needs_dict, tracked_receivers=None, filter=None):
    msg_needs = []
    if tracked_receivers is None:
        tracked_receivers = []
    for link_type in link_types:
        msg_needs += [all_needs_dict[x] for x in sender[link_type]]

    messages = {}
    p_string = ""
    c_string = ""
    for msg_need in msg_needs:
        messages[msg_need["id"]] = {"id": msg_need["id"], "title": msg_need["title"], "receivers": {}}
        if sender["id"] not in tracked_receivers:
            p_string += 'participant "{}" as {}\n'.format(sender["title"], sender["id"])
            tracked_receivers.append(sender["id"])
        for link_type in link_types:
            receiver_ids = msg_need[link_type]
            for rec_id in receiver_ids:
                if filter:
                    from sphinxcontrib.needs.filter_common import filter_single_need

                    if not filter_single_need(all_needs_dict[rec_id], filter, needs=all_needs_dict.values()):
                        continue

                rec_data = {"id": rec_id, "title": all_needs_dict[rec_id]["title"], "messages": []}

                c_string += "{} -> {}: {}\n".format(sender["id"], rec_data["id"], msg_need["title"])

                if rec_id not in tracked_receivers:
                    rec_messages, p_string_new, c_string_new = get_message_needs(
                        all_needs_dict[rec_id], link_types, all_needs_dict, tracked_receivers, filter=filter
                    )
                    p_string += p_string_new
                    c_string += c_string_new

                    rec_data["messages"] = rec_messages

                messages[msg_need["id"]]["receivers"][rec_id] = rec_data

    return messages, p_string, c_string


class NeedSequenceException(BaseException):
    """Errors during Sequence handling"""
