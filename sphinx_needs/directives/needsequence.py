from __future__ import annotations

import os
import re
from typing import Any, Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinxcontrib.plantuml import (
    generate_name,  # Need for plantuml filename calculation
)

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.diagrams_common import (
    DiagramBase,
    add_config,
    create_legend,
    get_debug_container,
    get_filter_para,
    no_plantuml,
)
from sphinx_needs.directives.utils import no_needs_found_paragraph
from sphinx_needs.filter_common import FilterBase
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import add_doc, remove_node_from_tree

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

    def run(self) -> Sequence[nodes.Node]:
        env = self.env

        _, targetid, targetnode = self.create_target("needsequence")

        start = self.options.get("start")
        if start is None or len(start.strip()) == 0:
            raise NeedSequenceException(
                "No valid start option given for needsequence. "
                f"See file {env.docname}:{self.lineno}"
            )

        # Add the needsequence and all needed information
        SphinxNeedsData(env).get_or_create_sequences()[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "start": self.options.get("start", ""),
            **self.collect_filter_attributes(),
            **self.collect_diagram_attributes(),
        }

        add_doc(env, env.docname)

        return [targetnode] + [Needsequence("")]


def process_needsequence(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    # Replace all needsequence nodes with a list of the collected needs.
    env = app.env
    needs_data = SphinxNeedsData(env)
    all_needs_dict = needs_data.get_or_create_needs()

    needs_config = NeedsSphinxConfig(env.config)
    include_needs = needs_config.include_needs
    link_type_names = [link["option"].upper() for link in needs_config.extra_links]
    needs_types = needs_config.types

    # NEEDSEQUENCE
    # for node in doctree.findall(Needsequence):
    for node in found_nodes:
        if not include_needs:
            remove_node_from_tree(node)
            continue

        id = node.attributes["ids"][0]
        current_needsequence = needs_data.get_or_create_sequences()[id]

        option_link_types = [
            link.upper() for link in current_needsequence["link_types"]
        ]
        for lt in option_link_types:
            if lt not in link_type_names:
                logger.warning(
                    "Unknown link type {link_type} in needsequence {flow}. Allowed values:"
                    " {link_types} [needs]".format(
                        link_type=lt,
                        flow=current_needsequence["target_id"],
                        link_types=",".join(link_type_names),
                    ),
                    type="needs",
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
        puml_node = plantuml(plantuml_block_text)

        # Add source origin
        puml_node.line = current_needsequence["lineno"]
        puml_node.source = env.doc2path(current_needsequence["docname"])

        puml_node["uml"] = "@startuml\n"

        # Adding config
        config = current_needsequence["config"]
        puml_node["uml"] += add_config(config)

        start_needs_id = [
            x.strip() for x in re.split(";|,", current_needsequence["start"])
        ]
        if len(start_needs_id) == 0:
            # TODO this should be a warning (and not tested)
            raise NeedSequenceException(
                "No start-id set for needsequence"
                f" docname {current_needsequence['docname']}"
                f":{current_needsequence['lineno']}"
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
                    "Given {} in needsequence unknown." " File {}" ":{}".format(
                        need_id,
                        current_needsequence["docname"],
                        current_needsequence["lineno"],
                    )
                )

            # Add children of participants
            _msg_receiver_needs, p_string_new, c_string_new = get_message_needs(
                app,
                need,
                current_needsequence["link_types"],
                all_needs_dict,
                filter=current_needsequence["filter"],
            )
            p_string += p_string_new
            c_string += c_string_new

        puml_node["uml"] += p_string

        puml_node["uml"] += "\n' Connection definition \n\n"
        puml_node["uml"] += c_string

        # Create a legend
        if current_needsequence["show_legend"]:
            puml_node["uml"] += create_legend(needs_types)

        puml_node["uml"] += "\n@enduml"
        puml_node["incdir"] = os.path.dirname(current_needsequence["docname"])
        puml_node["filename"] = os.path.split(current_needsequence["docname"])[
            1
        ]  # Needed for plantuml >= 0.9

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
            img_locaton = (
                "../" * subfolder_amount + "_images/" + gen_flow_link[0].split("/")[-1]
            )
            flow_ref = nodes.reference(
                "t", current_needsequence["caption"], refuri=img_locaton
            )
            puml_node += nodes.caption("", "", flow_ref)

        # Add lineno to node
        puml_node.line = current_needsequence["lineno"]

        content.append(puml_node)

        if (
            len(c_string) == 0 and p_string.count("participant") == 1
        ):  # no connections and just one (start) participant
            content = [
                (no_needs_found_paragraph(current_needsequence.get("filter_warning")))
            ]
        if current_needsequence["show_filters"]:
            content.append(get_filter_para(current_needsequence))

        if current_needsequence["debug"]:
            content += get_debug_container(puml_node)

        node.replace_self(content)


def get_message_needs(
    app: Sphinx,
    sender: NeedsInfoType,
    link_types: list[str],
    all_needs_dict: dict[str, NeedsInfoType],
    tracked_receivers: list[str] | None = None,
    filter: str | None = None,
) -> tuple[dict[str, dict[str, Any]], str, str]:
    msg_needs: list[dict[str, Any]] = []
    if tracked_receivers is None:
        tracked_receivers = []
    for link_type in link_types:
        msg_needs += [all_needs_dict[x] for x in sender[link_type]]  # type: ignore

    messages: dict[str, dict[str, Any]] = {}
    p_string = ""
    c_string = ""
    for msg_need in msg_needs:
        messages[msg_need["id"]] = {
            "id": msg_need["id"],
            "title": msg_need["title"],
            "receivers": {},
        }
        if sender["id"] not in tracked_receivers:
            p_string += 'participant "{}" as {}\n'.format(sender["title"], sender["id"])
            tracked_receivers.append(sender["id"])
        for link_type in link_types:
            receiver_ids = msg_need[link_type]
            for rec_id in receiver_ids:
                if filter:
                    from sphinx_needs.filter_common import filter_single_need

                    if not filter_single_need(
                        all_needs_dict[rec_id],
                        NeedsSphinxConfig(app.config),
                        filter,
                        needs=all_needs_dict.values(),
                    ):
                        continue

                rec_data = {
                    "id": rec_id,
                    "title": all_needs_dict[rec_id]["title"],
                    "messages": [],
                }

                c_string += "{} -> {}: {}\n".format(
                    sender["id"], rec_data["id"], msg_need["title"]
                )

                if rec_id not in tracked_receivers:
                    rec_messages, p_string_new, c_string_new = get_message_needs(
                        app,
                        all_needs_dict[rec_id],
                        link_types,
                        all_needs_dict,
                        tracked_receivers,
                        filter=filter,
                    )
                    p_string += p_string_new
                    c_string += c_string_new

                    rec_data["messages"] = rec_messages

                messages[msg_need["id"]]["receivers"][rec_id] = rec_data

    return messages, p_string, c_string


class NeedSequenceException(BaseException):
    """Errors during Sequence handling"""
