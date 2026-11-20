"""Unit tests of the resolver of ``_part_address.py``: what an address names where a need
is expected, one case for each clause of :func:`need_and_part_at`'s docstring."""

from __future__ import annotations

import pytest

from sphinx_needs._part_address import need_and_part_at, need_at
from sphinx_needs.data import NeedsInfoType
from sphinx_needs.need_item import NeedItem, NeedPartData, NeedsContent


def need(id: str, *parts: str) -> NeedItem:
    """A need with the given parts, and nothing the resolver does not read."""
    core: NeedsInfoType = {
        "id": id,
        "type": "req",
        "type_name": "Requirement",
        "type_prefix": "R_",
        "type_color": "#000000",
        "type_style": "node",
        "status": None,
        "tags": [],
        "constraints": (),
        "title": id,
        "collapse": False,
        "arch": {},
        "style": None,
        "layout": None,
        "hide": False,
        "external_css": "external_link",
        "has_dead_links": False,
        "has_forbidden_dead_links": False,
        "sections": (),
        "signature": None,
    }
    return NeedItem(
        core=core,
        content=NeedsContent(content="", doctype=".rst"),
        extras={},
        links={},
        parts=tuple(NeedPartData(id=part, content=part) for part in parts),
        source=None,
    )


def needs(*items: NeedItem) -> dict[str, NeedItem]:
    return {item["id"]: item for item in items}


def resolved(found: NeedItem | None) -> str | None:
    return None if found is None else found["id"]


def named(
    all_needs: dict[str, NeedItem], address: str
) -> tuple[str, str | None] | None:
    """What :func:`need_and_part_at` names, as the need's id and the part's id; checked
    against :func:`need_at`, which names its need."""
    found = need_and_part_at(all_needs, address)
    result = (
        None
        if found is None
        else (found.need["id"], None if found.part is None else found.part.id)
    )
    assert resolved(need_at(all_needs, address)) == (
        None if result is None else result[0]
    )
    return result


def test_an_address_naming_a_need_whole_is_that_need_before_it_is_split():
    """``DOT.1`` is the need ``DOT.1``, though ``DOT`` has a part ``1``: the address is
    read whole first, and names no part."""
    all_needs = needs(need("DOT", "1"), need("DOT.1"))
    assert named(all_needs, "DOT.1") == ("DOT.1", None)
    assert named(all_needs, "DOT") == ("DOT", None)


def test_an_address_is_split_at_its_first_dot():
    all_needs = needs(need("REQ_1", "a.b"), need("REQ_1.a", "b"))
    assert named(all_needs, "REQ_1.a.b") == ("REQ_1", "a.b")


def test_a_part_the_need_does_not_have_names_nothing():
    all_needs = needs(need("REQ_1", "p1"))
    assert named(all_needs, "REQ_1.p9") is None
    assert named(all_needs, "GONE.p1") is None


def test_a_namespace_stays_with_the_needs_id():
    all_needs = needs(need("nc::REQ_1", "p1"))
    assert named(all_needs, "nc::REQ_1.p1") == ("nc::REQ_1", "p1")


def test_a_condition_is_not_taken_off():
    """``REQ_1.p1[cond]`` names the part ``p1[cond]``, which ``REQ_1`` does not have."""
    all_needs = needs(need("REQ_1", "p1"))
    assert named(all_needs, "REQ_1.p1[cond]") is None


def test_the_empty_part_names_nothing_unless_the_need_has_it():
    """``REQ_1.`` names the part ``""``, which no need has: a need refuses a part with
    an empty id."""
    all_needs = needs(need("REQ_1", "p1"))
    assert named(all_needs, "REQ_1.") is None
    with pytest.raises(ValueError, match="non-empty string ID"):
        need("REQ_1", "")
