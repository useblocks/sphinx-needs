"""
NeedPart module
---------------
Provides the ability to mark specific parts of a need with an own id.

"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxRole
from sphinx.util.nodes import make_refnode

from sphinx_needs.data import NeedsInfoType, NeedsPartType
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.nodes import Need

LOGGER = get_logger(__name__)


class NeedPart(nodes.Inline, nodes.Element):
    @property
    def title(self) -> str:
        """Return the title of the part."""
        return self.attributes["title"]  # type: ignore[no-any-return]

    @property
    def part_id(self) -> str:
        """Return the ID of the part."""
        return self.attributes["part_id"]  # type: ignore[no-any-return]

    @property
    def need_id(self) -> str | None:
        """Return the ID of the need this part belongs to."""
        return self.attributes["need_id"]  # type: ignore[no-any-return]

    @need_id.setter
    def need_id(self, value: str) -> None:
        """Set the ID of the need this part belongs to."""
        self.attributes["need_id"] = value


_PART_PATTERN = re.compile(r"\(([\w-]+)\)(.*)", re.DOTALL)


class NeedPartRole(SphinxRole):
    """
    Role for need parts, which are sub-needs of a need.
    It is used to mark parts of a need with an own id.
    """

    def run(self) -> tuple[list[nodes.Node], list[nodes.system_message]]:
        # note self.text is the content of the role, with backslash escapes removed
        # TODO perhaps in a future change we should allow escaping parentheses in the part id?
        # and also strip (unescaped) space before/after the title
        result = _PART_PATTERN.match(self.text)
        if result:
            id_ = result.group(1)
            title = result.group(2)
        else:
            id_ = hashlib.sha1(self.text.encode("UTF-8")).hexdigest().upper()[:3]
            title = self.text
        part = NeedPart(title=title, part_id=id_, need_id=None)
        self.set_source_info(part)
        return [part], []


def process_need_part(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    # note this is called after needs have been processed and parts collected.
    for node in found_nodes:
        assert isinstance(node, NeedPart), "Expected NeedPart node"
        if node.need_id is None:
            log_warning(
                LOGGER,
                "Need part not associated with a need.",
                "part",
                node,
            )


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
        part_id = part_node.part_id

        if "parts" not in need:
            need["parts"] = {}

        if part_id in need["parts"]:
            log_warning(
                LOGGER,
                "part_need id {} in need {} is already taken. need_part may get overridden.".format(
                    part_id, need["id"]
                ),
                "duplicate_part_id",
                part_node,
            )

        need["parts"][part_id] = {
            "id": part_id,
            "content": part_node.title,
            "links": [],
            "links_back": [],
        }

        part_node.need_id = need["id"]
        part_id_ref = "{}.{}".format(need["id"], part_id)
        part_node["reftarget"] = part_id_ref

        node_need_part_line = nodes.inline(ids=[part_id_ref], classes=["need-part"])
        node_need_part_line.append(nodes.Text(part_node.title))

        if docname := need["docname"]:
            part_ref_node = make_refnode(
                app.builder, docname, docname, part_id_ref, nodes.Text(f" {part_id}")
            )
            part_ref_node["classes"] += ["needs-id"]
            node_need_part_line.append(part_ref_node)

        part_node.children = []
        part_node.append(node_need_part_line)


def find_parts(node: nodes.Node) -> list[NeedPart]:
    found_nodes = []
    for child in node.children:
        if isinstance(child, NeedPart):
            found_nodes.append(child)
        elif not isinstance(child, Need):  # parts in nested needs should be ignored
            found_nodes += find_parts(child)
    return found_nodes
