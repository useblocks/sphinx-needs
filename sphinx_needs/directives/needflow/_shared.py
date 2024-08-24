from __future__ import annotations

from typing import Literal

from sphinx_needs.config import LinkOptionsType
from sphinx_needs.data import (
    NeedsInfoType,
)
from sphinx_needs.logging import get_logger

logger = get_logger(__name__)


def filter_by_tree(
    all_needs: dict[str, NeedsInfoType],
    root_id: str,
    link_types: list[LinkOptionsType],
    direction: Literal["both", "incoming", "outgoing"],
    depth: int | None,
) -> dict[str, NeedsInfoType]:
    """Filter all needs by the given ``root_id``,
    and all needs that are connected to the root need by the given ``link_types``, in the given ``direction``."""
    need_items: dict[str, NeedsInfoType] = {}
    if root_id not in all_needs:
        return need_items
    roots = {root_id: (0, all_needs[root_id])}
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
    while roots:
        root_id, (root_depth, root) = roots.popitem()
        if root_id in need_items:
            continue
        if depth is not None and root_depth > depth:
            continue
        need_items[root_id] = root
        for link_type_name in links_to_process:
            roots.update(
                {
                    i: (root_depth + 1, all_needs[i])
                    for i in root.get(link_type_name, [])  # type: ignore[attr-defined]
                    if i in all_needs
                }
            )

    return need_items


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
