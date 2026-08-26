"""
Diagrams common module, which stores all class definitions and functions, which get reused in
diagram related directive. E.g. needflow and needsequence.
"""

from __future__ import annotations

import html
import os
import textwrap
from typing import TypedDict
from urllib.parse import urlparse

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.config import NeedsSphinxConfig, NeedType
from sphinx_needs.data import NeedsFilteredBaseType
from sphinx_needs.errors import NoUri
from sphinx_needs.logging import get_logger
from sphinx_needs.need_item import NeedItem, NeedPartItem
from sphinx_needs.utils import get_scale, split_link_types

logger = get_logger(__name__)


class DiagramAttributesType(TypedDict):
    show_legend: bool
    show_filters: bool
    show_link_names: bool
    link_types: list[str]
    config: str
    config_names: str
    scale: str
    highlight: str
    align: str | None
    debug: bool
    caption: str | None


class DiagramBase(SphinxDirective):
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

    def create_target(self, target_name: str) -> tuple[int, str, nodes.target]:
        id = self.env.new_serialno(target_name)
        targetid = f"{target_name}-{self.env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        return id, targetid, targetnode

    def collect_diagram_attributes(self) -> DiagramAttributesType:
        location = (self.env.docname, self.lineno)
        link_types = split_link_types(self.options.get("link_types", "links"), location)

        needs_config = NeedsSphinxConfig(self.config)
        config_names = self.options.get("config")
        configs = []
        if config_names:
            for config_name in config_names.split(","):
                config_name = config_name.strip()
                # TODO this is copied from NeedflowDirective, is it correct?
                if config_name and config_name in needs_config.flow_configs:
                    configs.append(needs_config.flow_configs[config_name])

        collected_diagram_options: DiagramAttributesType = {
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


def set_plantuml_paths(
    puml_node: nodes.Element, env: BuildEnvironment, docname: str
) -> None:
    """Point a generated PlantUML node at the physical location of ``docname``.

    ``sphinxcontrib-plantuml`` runs the PlantUML process with
    ``cwd = os.path.join(srcdir, node["incdir"])``, so ``incdir`` decides where
    relative ``!include`` paths are resolved. Deriving it from the *logical*
    docname breaks as soon as the document does not physically live under
    ``srcdir`` -- e.g. a document contributed by ``sphinx-mounts``, whose source
    file stays in an external tree. PlantUML then gets a non-existent ``cwd``,
    which surfaces as the misleading "plantuml command cannot be run".

    ``env.doc2path(docname, base=False)`` returns a srcdir-relative path for an
    ordinary document and the absolute external path for a mounted one. Since
    ``os.path.join`` discards its left operand when the right one is absolute,
    both cases resolve correctly -- and ordinary documents keep the exact
    ``incdir`` value they had before, so PlantUML's content-addressed cache
    stays valid (and machine-independent) for them.
    """
    puml_node["incdir"] = os.path.dirname(env.doc2path(docname, base=False))
    puml_node["filename"] = os.path.split(docname)[1]  # Needed for plantuml >= 0.9


def add_config(config: str) -> str:
    """Adds config section"""
    uml = ""
    if config and len(config) >= 3:
        # Remove all empty lines
        config = "\n".join(
            [line.strip() for line in config.split("\n") if line.strip()]
        )
        uml += "\n' Config\n\n"
        uml += config
        uml += "\n\n"
    return uml


def get_filter_para(node_element: NeedsFilteredBaseType) -> nodes.paragraph:
    """Return paragraph containing the used filter description"""
    para = nodes.paragraph()
    filter_text = "Used filter:"
    filter_text += (
        " status({})".format(" OR ".join(node_element["status"]))
        if len(node_element["status"]) > 0
        else ""
    )
    if len(node_element["status"]) > 0 and len(node_element["tags"]) > 0:
        filter_text += " AND "
    filter_text += (
        " tags({})".format(" OR ".join(node_element["tags"]))
        if len(node_element["tags"]) > 0
        else ""
    )
    if (len(node_element["status"]) > 0 or len(node_element["tags"]) > 0) and len(
        node_element["types"]
    ) > 0:
        filter_text += " AND "
    filter_text += (
        " types({})".format(" OR ".join(node_element["types"]))
        if len(node_element["types"]) > 0
        else ""
    )

    filter_node = nodes.emphasis(filter_text, filter_text)
    para += filter_node
    return para


def get_debug_container(puml_node: nodes.Element) -> nodes.container:
    """Return container containing the raw plantuml code"""
    debug_container = nodes.container()
    if isinstance(puml_node, nodes.figure):
        data = puml_node.children[0]["uml"]  # type: ignore[index]
    else:
        data = puml_node["uml"]
    data = "\n".join([html.escape(line) for line in data.split("\n")])
    debug_para = nodes.raw("", f"<pre>{data}</pre>", format="html")
    debug_container += debug_para

    return debug_container


def calculate_link(
    app: Sphinx,
    need_info: NeedItem | NeedPartItem,
    _fromdocname: None | str,
    relative: str = "..",
) -> str:
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
    builder = app.builder
    try:
        if need_info["is_external"]:
            assert need_info["external_url"] is not None, (
                "external_url must be set for external needs"
            )
            link = need_info["external_url"]
            # check if need_info["external_url"] is relative path
            parsed_url = urlparse(need_info["external_url"])
            if not parsed_url.scheme and not os.path.isabs(need_info["external_url"]):
                link = relative + "/" + need_info["external_url"]
        elif _docname := need_info["docname"]:
            link = (
                relative
                + "/"
                + builder.get_target_uri(_docname)
                + "#"
                + need_info["id_parent"]
            )
            if need_info["is_part"]:
                link = f"{link}.{need_info['id']}"

    except NoUri:
        link = ""

    return link


def create_legend(need_types: list[NeedType]) -> str:
    """Create the PlantUML legend for the given need types.

    :param need_types: The need types to document, in the order they are shown.
    :return: The PlantUML ``legend`` block.
    """

    def create_row(need_type: NeedType) -> str:
        # 'color' is optional, and a type without one keeps its row,
        # with an empty swatch cell, rather than being dropped from the legend
        color = need_type.get("color") or ""
        swatch = f"<back:{color}> {color} </back>" if color else " "
        return f"\n|{swatch}| {need_type['title']} |"

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
