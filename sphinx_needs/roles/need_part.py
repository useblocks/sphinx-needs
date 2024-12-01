"""
NeedPart module
---------------
Provides the ability to mark specific parts of a need with an own id.

Most voodoo is done in need.py

"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import cast

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.nodes import make_refnode

from sphinx_needs.data import NeedsInfoType, NeedsPartType
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.nodes import Need

log = get_logger(__name__)


class NeedPart(nodes.Inline, nodes.Element):
    pass


def process_need_part(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    pass


part_pattern = re.compile(r"\(([\w-]+)\)(.*)", re.DOTALL)


def create_need_from_part(need: NeedsInfoType, part: NeedsPartType) -> NeedsInfoType:
    """Create a full need from a part and its parent need."""
    full_part: NeedsInfoType = {**need, **part}
    full_part["id_complete"] = f"{need['id']}.{part['id']}"
    full_part["id_parent"] = need["id"]
    full_part["is_need"] = False
    full_part["is_part"] = True
    return full_part


def iter_need_parts(need: NeedsInfoType) -> Iterable[NeedsInfoType]:
    """Yield all parts, a.k.a sub-needs, from a need.

    A sub-need is a child of a need, which has its own ID,
    and overrides the content of the parent need.
    """
    for part in need["parts"].values():
        yield create_need_from_part(need, part)


def update_need_with_parts(
    env: BuildEnvironment, need: NeedsInfoType, part_nodes: list[NeedPart]
) -> None:
    app = env.app
    for part_node in part_nodes:
        content = cast(str, part_node.children[0].children[0])  # ->inline->Text
        result = part_pattern.match(content)
        if result:
            inline_id = result.group(1)
            part_content = result.group(2)
        else:
            part_content = content
            inline_id = (
                hashlib.sha1(part_content.encode("UTF-8")).hexdigest().upper()[:3]
            )

        if "parts" not in need:
            need["parts"] = {}

        if inline_id in need["parts"]:
            log_warning(
                log,
                "part_need id {} in need {} is already taken. need_part may get overridden.".format(
                    inline_id, need["id"]
                ),
                "duplicate_part_id",
                part_node,
            )

        need["parts"][inline_id] = {
            "id": inline_id,
            "content": part_content,
            "links": [],
            "links_back": [],
        }

        part_id_ref = "{}.{}".format(need["id"], inline_id)

        part_node["reftarget"] = part_id_ref

        part_text_node = nodes.Text(part_content)

        part_node.children = []
        node_need_part_line = nodes.inline(ids=[part_id_ref], classes=["need-part"])
        node_need_part_line.append(part_text_node)

        if docname := need["docname"]:
            part_id_show = inline_id
            part_link_text = f" {part_id_show}"
            part_link_node = nodes.Text(part_link_text)

            part_ref_node = make_refnode(
                app.builder, docname, docname, part_id_ref, part_link_node
            )
            part_ref_node["classes"] += ["needs-id"]
            node_need_part_line.append(part_ref_node)

        part_node.append(node_need_part_line)


def find_parts(node: nodes.Node) -> list[NeedPart]:
    found_nodes = []
    for child in node.children:
        if isinstance(child, NeedPart):
            found_nodes.append(child)
        elif not isinstance(child, Need):  # parts in nested needs should be ignored
            found_nodes += find_parts(child)
    return found_nodes
