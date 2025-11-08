"""Test the need item API."""

import pytest

from sphinx_needs.data import NeedsInfoType
from sphinx_needs.need_item import (
    NeedConstraintResults,
    NeedItem,
    NeedModification,
    NeedPartData,
    NeedsContent,
)


def core() -> NeedsInfoType:
    return {
        "id": "abc",
        "type": "type",
        "type_name": "type title",
        "type_prefix": "type prefix",
        "type_color": "#000000",
        "type_style": "node",
        "status": None,
        "tags": ["tag1"],
        "constraints": ("const1",),
        "title": "title",
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


def content(content: str = "content") -> NeedsContent:
    return NeedsContent(doctype=".rst", content=content)


def test_need_item_validate():
    with pytest.raises(TypeError, match="NeedItem core must be a dictionary."):
        NeedItem(core=1, content=content(), extras={}, links={}, source=None)

    with pytest.raises(
        TypeError, match="NeedItem content must be a NeedsContent instance."
    ):
        NeedItem(core=core(), content=1, extras={}, links={}, source=None)

    with pytest.raises(
        TypeError, match="NeedItem source must obey the NeeItemSourceProtocol."
    ):
        NeedItem(core=core(), content=content(), extras={}, links={}, source=1)

    with pytest.raises(TypeError, match="NeedItem extras must be a dictionary."):
        NeedItem(core=core(), content=content(), extras=1, links={}, source=None)

    with pytest.raises(TypeError, match="NeedItem links must be a dictionary."):
        NeedItem(core=core(), content=content(), extras={}, links=1, source=None)

    with pytest.raises(
        TypeError, match="NeedItem links must be a dictionary of lists of strings."
    ):
        NeedItem(
            core=core(), content=content(), extras={}, links={"a": [1]}, source=None
        )

    with pytest.raises(TypeError, match="NeedItem backlinks must be a dictionary."):
        NeedItem(
            core=core(),
            content=content(),
            extras={},
            links={},
            backlinks=1,
            source=None,
        )

    with pytest.raises(
        TypeError, match="NeedItem backlinks must be a dictionary of lists of strings."
    ):
        NeedItem(
            core=core(),
            content=content(),
            extras={},
            links={},
            backlinks={"a": [1]},
            source=None,
        )

    core_copy = core()
    del core_copy["id"]
    with pytest.raises(
        ValueError, match="NeedItem core missing required keys: \\['id'\\]"
    ):
        NeedItem(core=core_copy, content=content(), extras={}, links={}, source=None)

    with pytest.raises(
        ValueError, match="NeedItem core contains extra keys: \\['other'\\]"
    ):
        NeedItem(
            core=core() | {"other": "a"},
            content=content(),
            extras={},
            links={},
            source=None,
        )

    with pytest.raises(
        ValueError,
        match="NeedItem keys must be unique across core, computed, extras, links, and backlinks. Duplicate keys: \\['id', 'is_need', 'other'\\]",
    ):
        NeedItem(
            core=core(),
            content=content(),
            extras={"id": "value1", "is_need": "value2", "other": "x"},
            links={"other": ["y"]},
            source=None,
        )

    with pytest.raises(
        ValueError,
        match="Backlink keys must be the same as link keys, difference found: \\['a', 'b'\\]",
    ):
        NeedItem(
            core=core(),
            content=content(),
            extras={},
            links={"b": ["value1"]},
            backlinks={"a": ["value1"]},
            source=None,
        )


def test_need_item_get(snapshot):
    item = NeedItem(
        core=core(),
        content=content(),
        extras={"extra1": "value1", "extra2": "value2"},
        links={"link1": ["ref1"], "link2": ["ref2"]},
        backlinks={"link1": ["ref3"], "link2": []},
        source=None,
    )

    assert sorted(item) == snapshot(name="item_list")
    assert sorted(item.keys()) == snapshot(name="item_keys")
    assert {**item} == snapshot(name="item_unpacked")

    assert "id" in item
    assert "extra1" in item
    assert "docname" in item
    assert "link1" in item
    assert "link1_back" in item
    assert "non_existent" not in item

    with pytest.raises(KeyError, match="'non_existent'"):
        item["non_existent"]
    assert item.get("non_existent", "default") == "default"
    assert item["id"] == "abc"
    assert item.get("id") == "abc"
    assert item.get("extra1") == "value1"
    assert item["extra1"] == "value1"
    assert item.get("link1") == ["ref1"]
    assert item["link1"] == ["ref1"]
    assert item.get("link1_back") == ["ref3"]
    assert item["link1_back"] == ["ref3"]

    assert sorted(item.iter_extra_keys()) == ["extra1", "extra2"]
    assert sorted(item.iter_extra_items()) == [
        ("extra1", "value1"),
        ("extra2", "value2"),
    ]
    assert item.get_extra("extra1") == "value1"
    with pytest.raises(KeyError, match="'unknown_extra'"):
        item.get_extra("unknown_extra")
    assert sorted(item.iter_links_keys()) == ["link1", "link2"]
    assert sorted(item.iter_links_items()) == [("link1", ["ref1"]), ("link2", ["ref2"])]
    assert item.get_links("link1") == ["ref1"]
    with pytest.raises(KeyError, match="'unknown_link'"):
        item.get_links("unknown_link")
    assert sorted(item.iter_backlinks_items()) == [("link1", ["ref3"]), ("link2", [])]
    assert item.get_backlinks("link1") == ["ref3"]
    with pytest.raises(KeyError, match="'unknown_link'"):
        item.get_backlinks("unknown_link")


def test_need_item_set():
    item = NeedItem(
        core=core(),
        content=content(),
        extras={"extra1": "value1", "extra2": "value2"},
        links={"link1": ["ref1"], "link2": ["ref2"]},
        backlinks={"link1": ["ref3"], "link2": []},
        source=None,
    )

    with pytest.raises(
        KeyError, match="Only existing keys can be set, not: 'unknown_key'"
    ):
        item["unknown_key"] = 1

    item["extra1"] = "value3"
    assert item["extra1"] == "value3"

    with pytest.raises(TypeError):
        item["link1"] = 1

    with pytest.raises(TypeError):
        item["link1"] = [1]

    item["link1"] = ["ref4"]
    assert item["link1"] == ["ref4"]

    with pytest.raises(TypeError):
        item["link1_back"] = 1

    with pytest.raises(TypeError):
        item["link1_back"] = [1]

    item["link1_back"] = ["ref5"]
    assert item["link1_back"] == ["ref5"]


def test_need_mutations():
    item = NeedItem(
        core=core(),
        content=content(),
        extras={},
        links={},
        backlinks={},
        source=None,
    )
    assert item.modifications == ()

    assert item["modifications"] == 0
    assert item["is_modified"] is False

    item.add_modification(NeedModification(docname="doc1", lineno=1))
    assert item.modifications == (NeedModification(docname="doc1", lineno=1),)

    assert item["modifications"] == 1
    assert item["is_modified"] is True

    item.add_modification(NeedModification(docname="doc2", lineno=2))
    assert item.modifications == (
        NeedModification(docname="doc1", lineno=1),
        NeedModification(docname="doc2", lineno=2),
    )

    assert item["modifications"] == 2
    assert item["is_modified"] is True

    with pytest.raises(
        TypeError, match="modification must be a NeedModification instance."
    ):
        item.add_modification("not a modification")

    copied = item.copy()
    assert copied.modifications == (
        NeedModification(docname="doc1", lineno=1),
        NeedModification(docname="doc2", lineno=2),
    )
    assert copied["modifications"] == 2
    assert copied["is_modified"] is True

    assert copied.modifications == item.modifications


def test_need_constraints_results():
    item = NeedItem(
        core=core(),
        content=content(),
        extras={},
        links={},
        backlinks={},
        source=None,
    )
    assert item["constraints_results"] is None
    assert item["constraints_error"] is None
    assert item["constraints_passed"] is None

    with pytest.raises(
        TypeError,
        match="constraint_results must be a NeedConstraintResults instance or None.",
    ):
        item.set_constraint_results("not a NeedConstraintResults")

    with pytest.raises(
        ValueError,
        match="constraint_results keys must match the constraints defined in the need.",
    ):
        item.set_constraint_results(NeedConstraintResults({}))

    item.set_constraint_results(
        NeedConstraintResults(
            {
                "const1": (
                    ("check_0", True, None),
                    ("check_1", False, "error message"),
                ),
            }
        )
    )
    assert item["constraints_results"] == {
        "const1": {"check_0": True, "check_1": False},
    }
    assert item["constraints_error"] == "error message"
    assert item["constraints_passed"] is False

    copied = item.copy()
    assert copied["constraints_results"] == {
        "const1": {"check_0": True, "check_1": False},
    }
    assert copied["constraints_error"] == "error message"
    assert copied["constraints_passed"] is False

    assert item == copied

    copied.set_constraint_results(None)
    assert item != copied

    copied.set_constraint_results(
        NeedConstraintResults(
            {
                "const1": (
                    ("check_0", True, None),
                    ("check_1", False, "error message"),
                ),
            }
        )
    )
    assert item == copied


def test_need_part_item(snapshot):
    item = NeedItem(
        core=core(),
        parts=(
            NeedPartData(id="part1", content="Part 1", backlinks={"links": ["ref3"]}),
        ),
        content=content("Need 1"),
        extras={
            "extra1": "value1",
        },
        links={"links": ["ref1"], "other": ["ref2"]},
        backlinks={"links": ["ref2"], "other": []},
        source=None,
    )
    assert item["content"] == "Need 1"
    assert item.get_part_item("unknown") is None
    part = item.get_part_item("part1")
    assert part is not None
    assert part["is_need"] is False
    assert part["is_part"] is True
    assert part["id"] == "part1"
    assert part["id_complete"] == "abc.part1"
    assert part["id_parent"] == "abc"
    assert part["content"] == "Part 1"
    assert part["extra1"] == "value1"
    assert part["links"] == []
    assert part["links_back"] == ["ref3"]

    assert "docname" in part
    assert "unknown_key" not in part

    assert sorted(part.keys()) == snapshot(name="part_keys")
    assert sorted(part.items()) == snapshot(name="part_items")
    assert {**part} == snapshot(name="item_unpacked")
    assert sorted(part.iter_extra_keys()) == ["extra1"]
    assert sorted(part.iter_extra_items()) == [("extra1", "value1")]
    assert part.get_extra("extra1") == "value1"
    with pytest.raises(KeyError, match="'unknown_extra'"):
        part.get_extra("unknown_extra")
    assert sorted(part.iter_links_keys()) == ["links", "other"]
    assert sorted(part.iter_links_items()) == [("links", []), ("other", [])]
    assert part.get_links("other") == []
    with pytest.raises(KeyError, match="'unknown_link'"):
        part.get_links("unknown_link")
    assert sorted(part.iter_backlinks_items()) == [("links", ["ref3"]), ("other", [])]
    assert part.get_backlinks("links") == ["ref3"]
    with pytest.raises(KeyError, match="'unknown_link'"):
        part.get_backlinks("unknown_link")
