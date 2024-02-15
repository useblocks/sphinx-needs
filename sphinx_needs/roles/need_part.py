"""
NeedPart module
---------------
Provides the ability to mark specific parts of a need with an own id.

Most voodoo is done in need.py

"""

import hashlib
import re
from typing import List, cast

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.data import NeedsInfoType
from sphinx_needs.logging import get_logger

log = get_logger(__name__)


class NeedPart(nodes.Inline, nodes.Element):
    pass


def process_need_part(app: Sphinx, doctree: nodes.document, fromdocname: str, found_nodes: List[nodes.Element]) -> None:
    pass


part_pattern = re.compile(r"\(([\w-]+)\)(.*)")


def update_need_with_parts(env: BuildEnvironment, need: NeedsInfoType, part_nodes: List[NeedPart]) -> None:
    app = env.app
    builder = app.builder
    for part_node in part_nodes:
        content = cast(str, part_node.children[0].children[0])  # ->inline->Text
        result = part_pattern.match(content)
        if result:
            inline_id = result.group(1)
            part_content = result.group(2)
        else:
            part_content = content
            inline_id = hashlib.sha1(part_content.encode("UTF-8")).hexdigest().upper()[:3]

        if "parts" not in need:
            need["parts"] = {}

        if inline_id in need["parts"]:
            log.warning(
                "part_need id {} in need {} is already taken. need_part may get overridden. [needs]".format(
                    inline_id, need["id"]
                ),
                type="needs",
            )

        need["parts"][inline_id] = {
            "id": inline_id,
            "content": part_content,
            "document": need["docname"],
            "links_back": [],
            "is_part": True,
            "is_need": False,
            "links": [],
        }

        part_id_ref = "{}.{}".format(need["id"], inline_id)
        part_id_show = inline_id
        part_node["reftarget"] = part_id_ref

        part_link_text = f" {part_id_show}"
        part_link_node = nodes.Text(part_link_text)
        part_text_node = nodes.Text(part_content)

        from sphinx.util.nodes import make_refnode

        part_ref_node = make_refnode(builder, need["docname"], need["docname"], part_id_ref, part_link_node)
        part_ref_node["classes"] += ["needs-id"]

        part_node.children = []
        node_need_part_line = nodes.inline(ids=[part_id_ref], classes=["need-part"])
        node_need_part_line.append(part_text_node)
        node_need_part_line.append(part_ref_node)
        part_node.append(node_need_part_line)


def find_parts(node: nodes.Node) -> List[NeedPart]:
    found_nodes = []
    for child in node.children:
        if isinstance(child, NeedPart):
            found_nodes.append(child)
        else:
            found_nodes += find_parts(child)
    return found_nodes
