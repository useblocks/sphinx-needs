from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinxcontrib.plantuml import (
    generate_name,  # Need for plantuml filename calculation
)

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.diagrams_common import (
    DiagramBase,
    add_config,
    create_legend,
    get_debug_container,
    get_filter_para,
    no_plantuml,
)
from sphinx_needs.directives.utils import (
    SphinxNeedsLinkTypeException,
    no_needs_found_paragraph,
)
from sphinx_needs.filter_common import FilterBase, filter_single_need, process_filters
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import MONTH_NAMES, add_doc, remove_node_from_tree

logger = get_logger(__name__)


class Needgantt(nodes.General, nodes.Element):
    pass


class NeedganttDirective(FilterBase, DiagramBase):
    """
    Directive to get gantt diagrams.
    """

    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        "starts_with_links": directives.unchanged,
        "starts_after_links": directives.unchanged,
        "ends_with_links": directives.unchanged,
        "milestone_filter": directives.unchanged,
        "start_date": directives.unchanged,
        "timeline": directives.unchanged,
        "duration_option": directives.unchanged,
        "completion_option": directives.unchanged,
        "no_color": directives.flag,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)
    option_spec.update(DiagramBase.base_option_spec)

    def run(self) -> Sequence[nodes.Node]:
        env = self.env
        needs_config = NeedsSphinxConfig(env.config)

        _id, targetid, targetnode = self.create_target("needgantt")

        starts_with_links = self.get_link_type_option("starts_with_links")
        starts_after_links = self.get_link_type_option("starts_after_links", "links")
        ends_with_links = self.get_link_type_option("ends_with_links")

        milestone_filter = self.options.get("milestone_filter")
        start_date = self.options.get("start_date")
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                # datetime.fromisoformat(start_date) # > py3.7 only
            except Exception:
                raise NeedGanttException(
                    f"Given start date {start_date} is not valid. Please use YYYY-MM-DD as format. "
                    "E.g. 2020-03-27"
                )
        else:
            start_date = None  # If None we do not set a start date later

        timeline = self.options.get("timeline")
        timeline_options = ["daily", "weekly", "monthly"]
        if timeline and timeline not in timeline_options:
            raise NeedGanttException(
                "Given scale value {} is invalid. Please use: " "{}".format(
                    timeline, ",".join(timeline_options)
                )
            )
        else:
            timeline = None  # Timeline/scale not set later

        no_color = "no_color" in self.options

        duration_option = self.options.get(
            "duration_option", needs_config.duration_option
        )
        completion_option = self.options.get(
            "completion_option", needs_config.completion_option
        )

        # Add the needgantt and all needed information
        SphinxNeedsData(env).get_or_create_gantts()[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "starts_with_links": starts_with_links,
            "starts_after_links": starts_after_links,
            "ends_with_links": ends_with_links,
            "milestone_filter": milestone_filter,
            "start_date": start_date,
            "timeline": timeline,
            "no_color": no_color,
            "duration_option": duration_option,
            "completion_option": completion_option,
            **self.collect_filter_attributes(),
            **self.collect_diagram_attributes(),
        }

        add_doc(env, env.docname)

        gantt_node = Needgantt("")
        self.set_source_info(gantt_node)

        return [targetnode, gantt_node]

    def get_link_type_option(self, name: str, default: str = "") -> list[str]:
        link_types = [
            x.strip() for x in re.split(";|,", self.options.get(name, default))
        ]
        conf_link_types = NeedsSphinxConfig(self.env.config).extra_links
        conf_link_types_name = [x["option"] for x in conf_link_types]

        final_link_types = []
        for link_type in link_types:
            if link_type is None or link_type == "":
                continue
            if link_type not in conf_link_types_name:
                raise SphinxNeedsLinkTypeException(
                    link_type
                    + "does not exist in configuration option needs_extra_links"
                )

            final_link_types.append(link_type)
        return final_link_types


def process_needgantt(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    # Replace all needgantt nodes with a list of the collected needs.
    env = app.env
    needs_config = NeedsSphinxConfig(app.config)

    # link_types = needs_config.extra_links
    # allowed_link_types_options = [link.upper() for link in needs_config.flow_link_types]

    # NEEDGANTT
    # for node in doctree.findall(Needgantt):
    for node in found_nodes:
        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        id = node.attributes["ids"][0]
        current_needgantt = SphinxNeedsData(env).get_or_create_gantts()[id]
        all_needs_dict = SphinxNeedsData(env).get_or_create_needs()

        content = []
        try:
            if "sphinxcontrib.plantuml" not in app.config.extensions:
                raise ImportError
            from sphinxcontrib.plantuml import plantuml
        except ImportError:
            no_plantuml(node)
            continue

        plantuml_block_text = ".. plantuml::\n" "\n" "   @startgantt" "   @endgantt"
        puml_node = plantuml(plantuml_block_text)

        # Add source origin
        puml_node.line = current_needgantt["lineno"]
        puml_node.source = env.doc2path(current_needgantt["docname"])

        puml_node["uml"] = "@startgantt\n"

        # Adding config
        config = current_needgantt["config"]
        puml_node["uml"] += add_config(config)

        all_needs = list(all_needs_dict.values())
        found_needs = process_filters(app, all_needs, current_needgantt)

        # Scale/timeline handling
        if current_needgantt["timeline"]:
            puml_node["uml"] += "printscale {}\n".format(current_needgantt["timeline"])

        # Project start date handling
        start_date_string = current_needgantt["start_date"]
        start_date_plantuml = None
        if start_date_string:
            try:
                start_date = datetime.strptime(start_date_string, "%Y-%m-%d")
                # start_date = datetime.fromisoformat(start_date_string)  # > py3.7 only
            except Exception:
                raise NeedGanttException(
                    'start_date "{}"for needgantt is invalid. '
                    'File: {}:current_needgantt["lineno"]'.format(
                        start_date_string, current_needgantt["docname"]
                    )
                )

            month = MONTH_NAMES[int(start_date.strftime("%m"))]
            start_date_plantuml = start_date.strftime(f"%dth of {month} %Y")
        if start_date_plantuml:
            puml_node["uml"] += f"Project starts the {start_date_plantuml}\n"

        # Element handling
        puml_node["uml"] += "\n' Elements definition \n\n"
        el_completion_string = ""
        el_color_string = ""
        for need in found_needs:
            complete = None

            if current_needgantt["milestone_filter"]:
                is_milestone = filter_single_need(
                    need, needs_config, current_needgantt["milestone_filter"]
                )
            else:
                is_milestone = False

            if current_needgantt["milestone_filter"] and is_milestone:
                gantt_element = "[{}] as [{}] lasts 0 days\n".format(
                    need["title"], need["id"]
                )
            else:  # Normal gantt element handling
                duration_option = current_needgantt["duration_option"]
                duration = need[duration_option]  # type: ignore[literal-required]
                complete_option = current_needgantt["completion_option"]
                complete = need[complete_option]  # type: ignore[literal-required]
                if not (duration and duration.isdigit()):
                    need_location = (
                        f" (located: {need['docname']}:{need['lineno']})"
                        if need["docname"]
                        else ""
                    )
                    logger.warning(
                        "Duration not set or invalid for needgantt chart. "
                        f"Need: {need['id']!r}{need_location}. Duration: {duration!r} [needs.gantt]",
                        type="needs",
                        subtype="gantt",
                        location=node,
                    )
                    duration = 1
                gantt_element = "[{}] as [{}] lasts {} days\n".format(
                    need["title"], need["id"], duration
                )

            if complete:
                complete = complete.replace("%", "")
                el_completion_string += "[{}] is {}% completed\n".format(
                    need["title"], complete
                )

            el_color_string += "[{}] is colored in {}\n".format(
                need["title"], need["type_color"]
            )

            puml_node["uml"] += gantt_element

        puml_node["uml"] += "\n' Element links definition \n\n"
        puml_node["uml"] += (
            "\n' Deactivated, as currently supported by plantuml beta only"
        )

        puml_node["uml"] += "\n' Element completion definition \n\n"
        puml_node["uml"] += el_completion_string + "\n"

        puml_node["uml"] += "\n' Element color definition \n\n"
        if current_needgantt["no_color"]:
            puml_node["uml"] += "' Color support deactivated via flag"
        else:
            puml_node["uml"] += el_color_string + "\n"

        # Constrain handling
        puml_node["uml"] += "\n' Constraints definition \n\n"
        puml_node["uml"] += "\n' Constraints definition \n\n"
        for need in found_needs:
            if current_needgantt["milestone_filter"]:
                is_milestone = filter_single_need(
                    need, needs_config, current_needgantt["milestone_filter"]
                )
            else:
                is_milestone = False
            for con_type in (
                "starts_with_links",
                "starts_after_links",
                "ends_with_links",
            ):
                if is_milestone:
                    keyword = "happens"
                elif con_type in ["starts_with_links", "starts_after_links"]:
                    keyword = "starts"
                else:
                    keyword = "ends"

                if con_type in ["starts_after_links", "ends_with_links"]:
                    start_end_sync = "end"
                else:
                    start_end_sync = "start"

                for link_type in current_needgantt[con_type]:  # type: ignore[literal-required]
                    start_with_links = need[link_type]  # type: ignore[literal-required]
                    for start_with_link in start_with_links:
                        start_need = all_needs_dict[start_with_link]
                        gantt_constraint = "[{}] {} at [{}]'s " "{}\n".format(
                            need["id"], keyword, start_need["id"], start_end_sync
                        )
                        puml_node["uml"] += gantt_constraint

        # Create a legend
        if current_needgantt["show_legend"]:
            puml_node["uml"] += create_legend(needs_config.types)

        puml_node["uml"] += "\n@endgantt"
        puml_node["incdir"] = os.path.dirname(current_needgantt["docname"])
        puml_node["filename"] = os.path.split(current_needgantt["docname"])[
            1
        ]  # Needed for plantuml >= 0.9

        scale = int(current_needgantt["scale"])
        # if scale != 100:
        puml_node["scale"] = scale

        puml_node = nodes.figure("", puml_node)

        puml_node["align"] = current_needgantt["align"] or "center"

        if current_needgantt["caption"]:
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
            img_location = (
                "../" * subfolder_amount + "_images/" + gen_flow_link[0].split("/")[-1]
            )
            flow_ref = nodes.reference(
                "t", current_needgantt["caption"], refuri=img_location
            )
            puml_node += nodes.caption("", "", flow_ref)

        content.append(puml_node)

        if len(found_needs) == 0:
            content = [
                no_needs_found_paragraph(current_needgantt.get("filter_warning"))
            ]
        if current_needgantt["show_filters"]:
            content.append(get_filter_para(current_needgantt))

        if current_needgantt["debug"]:
            content += get_debug_container(puml_node)

        puml_node["class"] = ["needgantt"]
        node.replace_self(content)


class NeedGanttException(BaseException):
    """Errors during Gantt handling"""
