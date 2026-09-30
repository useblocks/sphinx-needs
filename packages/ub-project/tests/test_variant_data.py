"""The variant-data quartet: validate, load, merge, resolve.

Ported from both copies this package replaces -- ``packages/sphinx-needs/tests/
test_variant_data.py`` and ``packages/sphinx-mounts/tests/test_variant_data.py`` -- with
the two differences between those copies ruled: :func:`resolve_variant_data` always
returns a fresh mapping, and every failure is an :class:`ProjectConfigError` whose message
names the dotted path and the rule.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ub_project import (
    ProjectConfigError,
    deep_merge,
    load_variant_data_file,
    resolve_variant_data,
    validate_variant_data,
)

#: (file side, inline side) pairs covering every branch ``deep_merge`` has: scalar
#: override, nested partial, table/scalar swaps in both directions, array replacement,
#: empty sides, four-deep nesting, and ``False`` <-> ``True`` flips (the ones a naive
#: "falsy means absent" merge gets wrong).
MERGE_SHAPES: list[tuple[dict[str, Any], dict[str, Any]]] = [
    ({"a": 1}, {"a": 2}),
    ({"a": 1}, {"b": 2}),
    ({"n": {"x": 1, "y": 2}}, {"n": {"y": 3}}),
    ({"n": {"x": 1}}, {"n": "scalar"}),
    ({"n": "scalar"}, {"n": {"x": 1}}),
    ({"tags": ["a", "b"]}, {"tags": ["c"]}),
    ({}, {"a": 1}),
    ({"a": 1}, {}),
    ({}, {}),
    ({"deep": {"a": {"b": {"c": 1, "d": 2}}}}, {"deep": {"a": {"b": {"c": 9}}}}),
    ({"debug": False}, {"debug": True}),
    ({"debug": True}, {"debug": False}),
]


def _write(tmp_path: Path, payload: object, name: str = "vd.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestValidate:
    @pytest.mark.parametrize(
        "data",
        [
            {"a": 1, "b": "s", "c": True, "d": 1.5},
            {"nested": {"deep": {"x": 1}}},
            {"empty_list": []},
            {"uniform": ["a", "b"]},
            {"bools": [True, False]},
            {"floats": [1.5, 2.5]},
            {"empty_map": {}},
            {},
        ],
        ids=[
            "scalars",
            "nested",
            "empty-list",
            "uniform-list",
            "bool-list",
            "float-list",
            "empty-map",
            "empty",
        ],
    )
    def test_valid_shapes_pass(self, data: dict[str, Any]) -> None:
        validate_variant_data(data)

    @pytest.mark.parametrize(
        ("data", "match"),
        [
            ("not a table", r"^var: variant data must be a table, got str$"),
            ({1: "x"}, r"^var: keys must be strings, got int 1$"),
            ({"a": {"b": None}}, r"^var\.a\.b: a value must be a .*got NoneType$"),
            ({"a": (1, 2)}, r"^var\.a: a value must be a .*got tuple$"),
            (
                {"a": [1, "x"]},
                r"^var\.a\[1\]: an array must hold one type, expected int but got str$",
            ),
            ({"a": [{"x": 1}]}, r"^var\.a: array elements must be a .*got dict$"),
            ({"a": [[1]]}, r"^var\.a: array elements must be a .*got list$"),
        ],
        ids=[
            "not-a-table",
            "non-str-key",
            "none-leaf",
            "tuple",
            "mixed-list",
            "list-of-tables",
            "list-of-lists",
        ],
    )
    def test_invalid_shapes_name_the_path_and_the_rule(
        self, data: Any, match: str
    ) -> None:
        with pytest.raises(ProjectConfigError, match=match):
            validate_variant_data(data)

    def test_bool_and_int_are_not_conflated_in_an_array(self) -> None:
        """``bool`` is an ``int`` subclass; an array is checked by EXACT type."""
        with pytest.raises(ProjectConfigError, match=r"expected int but got bool"):
            validate_variant_data({"vals": [1, True, 2]})
        with pytest.raises(ProjectConfigError, match=r"expected bool but got int"):
            validate_variant_data({"vals": [True, 1, False]})

    def test_int_and_float_are_not_conflated_in_an_array(self) -> None:
        with pytest.raises(ProjectConfigError, match=r"expected int but got float"):
            validate_variant_data({"vals": [1, 1.5]})

    def test_the_path_prefix_is_the_callers(self) -> None:
        with pytest.raises(
            ProjectConfigError, match=r"^needs\.variant_data\.build\.opt:"
        ):
            validate_variant_data({"build": {"opt": None}}, "needs.variant_data")


class TestLoad:
    def test_loads_a_json_object(self, tmp_path: Path) -> None:
        data = {"cpu": "arm", "nested": {"key": "val"}}
        assert load_variant_data_file(_write(tmp_path, data)) == data

    def test_accepts_a_string_path(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"cpu": "arm"})
        assert load_variant_data_file(str(path)) == {"cpu": "arm"}

    def test_a_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "absent.json"
        with pytest.raises(
            ProjectConfigError, match="variant data file not found"
        ) as info:
            load_variant_data_file(path)
        assert str(path) in str(info.value)

    def test_a_directory_is_reported_as_one(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectConfigError, match="is a directory") as info:
            load_variant_data_file(tmp_path)
        assert str(tmp_path) in str(info.value)

    def test_undecodable_json(self, tmp_path: Path) -> None:
        path = tmp_path / "vd.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ProjectConfigError, match="is not valid JSON") as info:
            load_variant_data_file(path)
        assert str(path) in str(info.value)

    def test_undecodable_bytes(self, tmp_path: Path) -> None:
        path = tmp_path / "vd.json"
        path.write_bytes(b'{"a": "\xff"}')
        with pytest.raises(ProjectConfigError, match="is not valid JSON"):
            load_variant_data_file(path)

    @pytest.mark.parametrize("payload", [[1, 2], "text", 3, None])
    def test_the_top_level_must_be_an_object(
        self, tmp_path: Path, payload: object
    ) -> None:
        with pytest.raises(ProjectConfigError, match="must hold a JSON object"):
            load_variant_data_file(_write(tmp_path, payload))

    def test_the_file_is_held_to_the_same_shape_rules(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"build": {"tags": [1, "x"]}})
        with pytest.raises(ProjectConfigError) as info:
            load_variant_data_file(path)
        message = str(info.value)
        assert str(path) in message
        assert r"var.build.tags[1]: an array must hold one type" in message


class TestDeepMerge:
    def test_simple(self) -> None:
        assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_override_wins(self) -> None:
        assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_recurses_only_when_both_sides_are_tables(self) -> None:
        assert deep_merge({"n": {"x": 1, "y": 2}}, {"n": {"y": 3}}) == {
            "n": {"x": 1, "y": 3}
        }
        assert deep_merge({"n": {"x": 1}}, {"n": "s"}) == {"n": "s"}
        assert deep_merge({"n": "s"}, {"n": {"x": 1}}) == {"n": {"x": 1}}
        assert deep_merge({"t": ["a", "b"]}, {"t": ["c"]}) == {"t": ["c"]}

    @pytest.mark.parametrize(
        ("base", "override"), MERGE_SHAPES, ids=range(len(MERGE_SHAPES))
    )
    def test_does_not_mutate_either_side(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> None:
        base_before = json.loads(json.dumps(base))
        override_before = json.loads(json.dumps(override))
        deep_merge(base, override)
        assert base == base_before
        assert override == override_before

    @pytest.mark.parametrize(
        ("base", "override"), MERGE_SHAPES, ids=range(len(MERGE_SHAPES))
    )
    def test_is_idempotent(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> None:
        """``deep_merge(base, already_merged) == already_merged``, for every shape."""
        merged = deep_merge(base, override)
        assert deep_merge(base, merged) == merged

    def test_returns_a_new_mapping(self) -> None:
        base = {"a": 1}
        override: dict[str, Any] = {}
        merged = deep_merge(base, override)
        assert merged is not base
        assert merged is not override

    def test_a_merged_level_is_new_and_the_inputs_survive_changing_it(self) -> None:
        base = {"n": {"x": 1}}
        merged = deep_merge(base, {"n": {"y": 2}})
        merged["n"]["z"] = 3
        assert base == {"n": {"x": 1}}


class TestResolve:
    def test_the_file_first_and_inline_merged_on_top(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            {"edition": "base", "cpu": "arm", "build": {"opt": 2, "debug": False}},
        )
        inline = {"edition": "pro", "build": {"debug": True}}
        assert resolve_variant_data(inline, path) == {
            "edition": "pro",
            "cpu": "arm",
            "build": {"opt": 2, "debug": True},
        }

    def test_only_a_file(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"edition": "base", "build": {"opt": 2}})
        assert resolve_variant_data(None, path) == {
            "edition": "base",
            "build": {"opt": 2},
        }
        assert resolve_variant_data({}, path) == {
            "edition": "base",
            "build": {"opt": 2},
        }

    def test_only_inline(self) -> None:
        assert resolve_variant_data({"edition": "pro"}, None) == {"edition": "pro"}

    def test_neither_is_the_empty_map(self) -> None:
        assert resolve_variant_data(None, None) == {}
        assert resolve_variant_data({}, None) == {}

    def test_a_malformed_inline_map(self) -> None:
        with pytest.raises(ProjectConfigError, match="an array must hold one type"):
            resolve_variant_data({"a": [1, "x"]}, None)

    def test_a_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectConfigError, match="not found"):
            resolve_variant_data({"a": 1}, tmp_path / "absent.json")

    def test_returns_a_fresh_mapping_with_no_file(self) -> None:
        """The ruled difference: never *inline* itself, even when it is the whole map.

        sphinx-needs' copy returned ``variant_data or base`` -- the caller's own object
        -- when only one side was set. A consumer storing the result and later changing
        it would then change its own configuration value.
        """
        inline = {"edition": "pro"}
        resolved = resolve_variant_data(inline, None)
        assert resolved == inline
        assert resolved is not inline
        resolved["edition"] = "changed"
        assert inline == {"edition": "pro"}

    def test_returns_a_fresh_mapping_with_an_empty_inline_table(
        self, tmp_path: Path
    ) -> None:
        empty: dict[str, Any] = {}
        resolved = resolve_variant_data(empty, None)
        assert resolved == {}
        assert resolved is not empty
        path = _write(tmp_path, {"a": 1})
        from_file = resolve_variant_data(empty, path)
        assert from_file is not empty

    def test_is_idempotent_over_an_already_merged_inline_map(
        self, tmp_path: Path
    ) -> None:
        """Feeding a merged map back in with the same file returns the same map."""
        path = _write(tmp_path, {"edition": "base", "cpu": "arm", "build": {"opt": 2}})
        inline = {"edition": "pro", "build": {"debug": True}}
        once = resolve_variant_data(inline, path)
        assert resolve_variant_data(once, path) == once
