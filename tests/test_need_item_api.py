"""Test the need item API."""

import pytest

from sphinx_needs.need_item import NeedItem


def test_need_item_validate():
    with pytest.raises(TypeError, match="NeedItem core must be a dictionary."):
        NeedItem(core=1, extras={}, links={}, source=None)

    with pytest.raises(TypeError, match="NeedItem extras must be a dictionary."):
        NeedItem(core={}, extras=1, links={}, source=None)

    with pytest.raises(TypeError, match="NeedItem links must be a dictionary."):
        NeedItem(core={}, extras={}, links=1, source=None)

    with pytest.raises(
        TypeError, match="NeedItem links must be a dictionary of lists of strings."
    ):
        NeedItem(core={}, extras={}, links={"a": [1]}, source=None)

    with pytest.raises(TypeError, match="NeedItem backlinks must be a dictionary."):
        NeedItem(core={}, extras={}, links={}, backlinks=1, source=None)

    with pytest.raises(
        TypeError, match="NeedItem backlinks must be a dictionary of lists of strings."
    ):
        NeedItem(core={}, extras={}, links={}, backlinks={"a": [1]}, source=None)

    with pytest.raises(ValueError, match="NeedItem core must contain key 'id'."):
        NeedItem(core={}, extras={}, links={}, source=None)

    with pytest.raises(
        ValueError, match="NeedItem core must have 'is_need' set to True."
    ):
        NeedItem(core={"id": "abc", "is_need": False}, extras={}, links={}, source=None)

    with pytest.raises(
        ValueError, match="NeedItem core must have 'is_part' set to False."
    ):
        NeedItem(
            core={"id": "abc", "is_need": True, "is_part": True},
            extras={},
            links={},
            source=None,
        )

    with pytest.raises(
        ValueError,
        match="NeedItem keys must be unique across core, extras, links, and backlinks. Duplicate keys: \\['id'\\]",
    ):
        NeedItem(
            core={"id": "abc", "is_need": True},
            extras={"id": "value1"},
            links={},
            source=None,
        )

    with pytest.raises(
        ValueError,
        match="NeedItem keys must be unique across core, extras, links, and backlinks. Duplicate keys: \\['id'\\]",
    ):
        NeedItem(
            core={"id": "abc", "is_need": True},
            extras={},
            links={"id": ["value1"]},
            source=None,
        )

    with pytest.raises(
        ValueError,
        match="Backlink keys must be the same as link keys, difference found: \\['a', 'b'\\]",
    ):
        NeedItem(
            core={"id": "abc", "is_need": True},
            extras={},
            links={"b": ["value1"]},
            backlinks={"a": ["value1"]},
            source=None,
        )


def test_need_item_get():
    item = NeedItem(
        core={"id": "abc"},
        extras={"extra1": "value1", "extra2": "value2"},
        links={"link1": ["ref1"], "link2": ["ref2"]},
        backlinks={"link1": ["ref3"], "link2": []},
        source=None,
    )

    assert sorted(item) == [
        "docname",
        "external_url",
        "extra1",
        "extra2",
        "id",
        "is_external",
        "is_import",
        "lineno",
        "lineno_content",
        "link1",
        "link1_back",
        "link2",
        "link2_back",
    ]
    assert sorted(item.keys()) == [
        "docname",
        "external_url",
        "extra1",
        "extra2",
        "id",
        "is_external",
        "is_import",
        "lineno",
        "lineno_content",
        "link1",
        "link1_back",
        "link2",
        "link2_back",
    ]
    assert {**item} == {
        "id": "abc",
        "extra1": "value1",
        "extra2": "value2",
        "link1": ["ref1"],
        "link2": ["ref2"],
        "link1_back": ["ref3"],
        "link2_back": [],
        "docname": None,
        "lineno": None,
        "lineno_content": None,
        "external_url": None,
        "is_import": False,
        "is_external": False,
    }

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
        core={"id": "abc"},
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


def test_need_part_item():
    item = NeedItem(
        core={
            "id": "abc",
            "content": "Need 1",
            "parts": {
                "part1": {
                    "id": "part1",
                    "content": "Part 1",
                    "links": [],
                    "links_back": ["ref3"],
                }
            },
        },
        extras={
            "extra1": "value1",
        },
        links={"links": ["ref1"], "other": ["ref2"]},
        backlinks={"links": ["ref2"], "other": []},
        source=None,
    )
    assert item["content"] == "Need 1"
    assert item.get_part("unknown") is None
    part = item.get_part("part1")
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

    assert sorted(part.keys()) == [
        "content",
        "docname",
        "external_url",
        "extra1",
        "id",
        "id_complete",
        "id_parent",
        "is_external",
        "is_import",
        "is_need",
        "is_part",
        "lineno",
        "lineno_content",
        "links",
        "links_back",
        "other",
        "other_back",
        "parts",
    ]
    assert sorted(part.items()) == [
        ("content", "Part 1"),
        ("docname", None),
        ("external_url", None),
        ("extra1", "value1"),
        ("id", "part1"),
        ("id_complete", "abc.part1"),
        ("id_parent", "abc"),
        ("is_external", False),
        ("is_import", False),
        ("is_need", False),
        ("is_part", True),
        ("lineno", None),
        ("lineno_content", None),
        ("links", []),
        ("links_back", ["ref3"]),
        ("other", ["ref2"]),
        ("other_back", []),
        (
            "parts",
            {
                "part1": {
                    "id": "part1",
                    "content": "Part 1",
                    "links": [],
                    "links_back": ["ref3"],
                }
            },
        ),
    ]
    assert {**part} == {
        "is_part": True,
        "lineno_content": None,
        "other": ["ref2"],
        "id_parent": "abc",
        "is_import": False,
        "lineno": None,
        "links_back": ["ref3"],
        "is_need": False,
        "external_url": None,
        "docname": None,
        "content": "Part 1",
        "parts": {
            "part1": {
                "id": "part1",
                "content": "Part 1",
                "links": [],
                "links_back": ["ref3"],
            }
        },
        "id_complete": "abc.part1",
        "links": [],
        "id": "part1",
        "other_back": [],
        "is_external": False,
        "extra1": "value1",
    }

    assert sorted(part.iter_extra_keys()) == ["extra1"]
    assert sorted(part.iter_extra_items()) == [("extra1", "value1")]
    assert part.get_extra("extra1") == "value1"
    with pytest.raises(KeyError, match="'unknown_extra'"):
        part.get_extra("unknown_extra")
    assert sorted(part.iter_links_keys()) == ["links", "other"]
    assert sorted(part.iter_links_items()) == [("links", []), ("other", ["ref2"])]
    assert part.get_links("other") == ["ref2"]
    with pytest.raises(KeyError, match="'unknown_link'"):
        part.get_links("unknown_link")
    assert sorted(part.iter_backlinks_items()) == [("links", ["ref3"]), ("other", [])]
    assert part.get_backlinks("links") == ["ref3"]
    with pytest.raises(KeyError, match="'unknown_link'"):
        part.get_backlinks("unknown_link")
