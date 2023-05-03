"""
Diagrams common module, which stores all class definitions and functions, which get reused in
diagram related directive. E.g. needflow and needsequence.
"""

import html
import os
import re
import textwrap
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.errors import NoUri
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import unwrap

logger = get_logger(__name__)


class DiagramBase(Directive):
    has_content = True

    base_option_spec = {
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

    def prepare_env(self, env_var: str) -> str:
        env = self.state.document.settings.env
        env_var = "need_all_" + env_var
        if not hasattr(env, env_var):
            setattr(env, env_var, {})

        # be sure, global var is available. If not, create it
        if not hasattr(env, "needs_all_needs"):
            env.needs_all_needs = {}

        return env_var

    def create_target(self, target_name: str) -> Tuple[int, str, nodes.target]:
        env: BuildEnvironment = self.state.document.settings.env
        id = env.new_serialno(target_name)
        targetid = f"{target_name}-{env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        return id, targetid, targetnode

    def collect_diagram_attributes(self) -> Dict[str, Any]:
        env = self.state.document.settings.env

        link_types = self.options.get("link_types", "links")
        if len(link_types) > 0:
            link_types = [link_type.strip() for link_type in re.split(";|,", link_types)]
            for i in range(len(link_types)):
                if len(link_types[i]) == 0 or link_types[i].isspace():
                    del link_types[i]
                    logger.warning(
                        "Scruffy link_type definition found in needsequence. " "Defined link_type contains spaces only."
                    )

        config_names = self.options.get("config")
        configs = []
        if config_names:
            for config_name in config_names.split(","):
                config_name = config_name.strip()
                if config_name and config_name in env.config.needs_flow_configs:
                    configs.append(env.config.needs_flow_configs[config_name])

        scale = self.options.get("scale", "100").replace("%", "")
        if not scale.isdigit():
            raise Exception(f'Needsequence scale value must be a number. "{scale}" found')
        if int(scale) < 1 or int(scale) > 300:
            raise Exception(f'Needsequence scale value must be between 1 and 300. "{scale}" found')

        highlight = self.options.get("highlight", "")

        caption = None
        if self.arguments:
            caption = self.arguments[0]

        collected_diagram_options = {
            "show_legend": "show_legend" in self.options,
            "show_filters": "show_filters" in self.options,
            "show_link_names": "show_link_names" in self.options,
            "link_types": link_types,
            "config": "\n".join(configs),
            "config_names": config_names,
            "scale": scale,
            "highlight": highlight,
            "align": self.options.get("align"),
            "debug": "debug" in self.options,
            "caption": caption,
        }
        return collected_diagram_options


def make_entity_name(name: str) -> str:
    """Creates a valid PlantUML entity name from the given value."""
    invalid_chars = "-=!#$%^&*[](){}/~'`<>:;"
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name


def no_plantuml(node: nodes.Element) -> None:
    """Adds a hint that plantuml is not available"""
    content = nodes.error()
    para = nodes.paragraph()
    text = nodes.Text("PlantUML is not available!")
    para += text
    content.append(para)
    node.replace_self(content)


def add_config(config: str) -> str:
    """Adds config section"""
    uml = ""
    if config and len(config) >= 3:
        # Remove all empty lines
        config = "\n".join([line.strip() for line in config.split("\n") if line.strip()])
        uml += "\n' Config\n\n"
        uml += config
        uml += "\n\n"
    return uml


def get_filter_para(node_element: nodes.Element) -> nodes.paragraph:
    """Return paragraph containing the used filter description"""
    para = nodes.paragraph()
    filter_text = "Used filter:"
    filter_text += " status(%s)" % " OR ".join(node_element["status"]) if len(node_element["status"]) > 0 else ""
    if len(node_element["status"]) > 0 and len(node_element["tags"]) > 0:
        filter_text += " AND "
    filter_text += " tags(%s)" % " OR ".join(node_element["tags"]) if len(node_element["tags"]) > 0 else ""
    if (len(node_element["status"]) > 0 or len(node_element["tags"]) > 0) and len(node_element["types"]) > 0:
        filter_text += " AND "
    filter_text += " types(%s)" % " OR ".join(node_element["types"]) if len(node_element["types"]) > 0 else ""

    filter_node = nodes.emphasis(filter_text, filter_text)
    para += filter_node
    return para


def get_debug_container(puml_node: nodes.Node) -> nodes.container:
    """Return container containing the raw plantuml code"""
    debug_container = nodes.container()
    if isinstance(puml_node, nodes.figure):
        data = puml_node.children[0]["uml"]
    else:
        data = puml_node["uml"]
    data = "\n".join([html.escape(line) for line in data.split("\n")])
    debug_para = nodes.raw("", f"<pre>{data}</pre>", format="html")
    debug_container += debug_para

    return debug_container


def calculate_link(app: Sphinx, need_info: Dict[str, Any], _fromdocname: str) -> str:
    """
    Link calculation
    All links we can get from docutils functions will be relative.
    But the generated link in the svg will be relative to the svg-file location
    (e.g. server.com/docs/_images/sqwxo499cnq329439dfjne.svg)
    and not to current documentation. Therefore we need to add ../ to get out of the image folder.

    :param app:
    :param need_info:
    :param fromdocname:
    :return:
    """
    builder = unwrap(app.builder)
    try:
        if need_info["is_external"]:
            link: str = need_info["external_url"]
            # check if need_info["external_url"] is relative path
            parsed_url = urlparse(need_info["external_url"])
            if not parsed_url.scheme and not os.path.isabs(need_info["external_url"]):
                # only need to add ../ or ..\ to get out of the image folder
                link = ".." + os.path.sep + need_info["external_url"]
        else:
            # link = "../" + builder.get_target_uri(need_info["docname"]) + "#" + need_info["target_node"]["refid"]
            link = "../" + builder.get_target_uri(need_info["docname"]) + "#" + need_info["target_id"]
            if need_info["is_part"]:
                link = f"{link}.{need_info['id']}"

    except NoUri:
        link = ""

    return link


def create_legend(need_types: List[Dict[str, Any]]) -> str:
    def create_row(need_type: Dict[str, Any]) -> str:
        return "\n|<back:{color}> {color} </back>| {name} |".format(color=need_type["color"], name=need_type["title"])

    rows = map(create_row, need_types)
    table = "|= Color |= Type |" + "".join(rows)

    legend = textwrap.dedent(
        """
        ' Legend definition
        legend
        {color_table}
        endlegend
        """
    )
    legend = legend.format(color_table=table)
    return legend
