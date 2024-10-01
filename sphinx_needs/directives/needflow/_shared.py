from __future__ import annotations

from typing import Literal

from docutils import nodes

from sphinx_needs.config import LinkOptionsType
from sphinx_needs.data import NeedsFlowType, NeedsInfoType
from sphinx_needs.logging import get_logger
from sphinx_needs.views import NeedsView

logger = get_logger(__name__)


def filter_by_tree(
    needs_view: NeedsView,
    root_id: str,
    link_types: list[LinkOptionsType],
    direction: Literal["both", "incoming", "outgoing"],
    depth: int | None,
) -> NeedsView:
    """Filter all needs by the given ``root_id``,
    and all needs that are connected to the root need by the given ``link_types``, in the given ``direction``."""
    if root_id not in needs_view:
        return needs_view.filter_ids([])
    roots = {root_id: (0, needs_view[root_id])}
    link_prefixes = (
        ("_back",)
        if direction == "incoming"
        else ("",)
        if direction == "outgoing"
        else ("", "_back")
    )
    links_to_process = [
        link["option"] + d for link in link_types for d in link_prefixes
    ]

    need_ids: list[str] = []
    while roots:
        root_id, (root_depth, root) = roots.popitem()
        if root_id in need_ids:
            continue
        if depth is not None and root_depth > depth:
            continue
        need_ids.append(root_id)
        for link_type_name in links_to_process:
            roots.update(
                {
                    i: (root_depth + 1, needs_view[i])
                    for i in root.get(link_type_name, [])  # type: ignore[attr-defined]
                    if i in needs_view
                }
            )

    return needs_view.filter_ids(need_ids)


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


def create_filter_paragraph(data: NeedsFlowType) -> nodes.paragraph:
    para = nodes.paragraph()
    filter_text = "Used filter:"
    filter_text += (
        " status({})".format(" OR ".join(data["status"]))
        if len(data["status"]) > 0
        else ""
    )
    if len(data["status"]) > 0 and len(data["tags"]) > 0:
        filter_text += " AND "
    filter_text += (
        " tags({})".format(" OR ".join(data["tags"])) if len(data["tags"]) > 0 else ""
    )
    if (len(data["status"]) > 0 or len(data["tags"]) > 0) and len(data["types"]) > 0:
        filter_text += " AND "
    filter_text += (
        " types({})".format(" OR ".join(data["types"]))
        if len(data["types"]) > 0
        else ""
    )

    filter_node = nodes.emphasis(filter_text, filter_text)
    para += filter_node

    return para
