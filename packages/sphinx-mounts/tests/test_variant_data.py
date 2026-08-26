"""The private copy of sphinx-needs' variant-data semantics.

sphinx-mounts computes the merged variant map itself. It never imports
sphinx-needs, never depends on it and never version-gates against it — and it
still cannot disagree with it, because the merge is **idempotent**: whenever
sphinx-needs is present and has already merged, its result is this merge's
*input*, and re-merging changes nothing.

The idempotency is what removes the version matrix, so it is measured here over
every shape ``deep_merge`` can produce rather than asserted once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_mounts.variants import (
    VariantDataError,
    deep_merge,
    load_variant_data_file,
    resolve_variant_data,
    validate_variant_data,
)

#: (file side, inline side) pairs covering every branch ``deep_merge`` has.
#:
#: Lifted from the recon probe that measured sphinx-needs' own ``deep_merge``
#: over the same shapes: scalar override, nested partial, mapping/scalar swaps
#: in both directions, list replacement, empty sides, four-deep nesting, and a
#: ``False`` -> ``True`` flip (the one a naive "falsy means absent" merge gets
#: wrong).
MERGE_SHAPES: list[tuple[dict[str, Any], dict[str, Any]]] = [
    ({"a": 1}, {"a": 2}),
    ({"n": {"x": 1, "y": 2}}, {"n": {"y": 3}}),
    ({"n": {"x": 1}}, {"n": "scalar"}),
    ({"n": "scalar"}, {"n": {"x": 1}}),
    ({"tags": ["a", "b"]}, {"tags": ["c"]}),
    ({}, {"a": 1}),
    ({"a": 1}, {}),
    ({"deep": {"a": {"b": {"c": 1, "d": 2}}}}, {"deep": {"a": {"b": {"c": 9}}}}),
    ({"debug": False}, {"debug": True}),
    ({"debug": True}, {"debug": False}),
]


@pytest.mark.parametrize(
    ("base", "override"), MERGE_SHAPES, ids=range(len(MERGE_SHAPES))
)
def test_the_merge_is_idempotent(
    base: dict[str, Any], override: dict[str, Any]
) -> None:
    """``deep_merge(file, already_merged) == already_merged``.

    This is the single property that lets one unconditional read rule be
    correct against every sphinx-needs state — absent, pre-resolution, and
    post-resolution — with no version sniffing and no feature detection.
    """
    merged = deep_merge(base, override)
    assert deep_merge(base, merged) == merged


def test_deep_merge_recurses_only_when_both_sides_are_mappings() -> None:
    """A list replaces a list; a scalar replaces a mapping and vice versa."""
    assert deep_merge({"n": {"x": 1, "y": 2}}, {"n": {"y": 3}}) == {
        "n": {"x": 1, "y": 3}
    }
    assert deep_merge({"n": {"x": 1}}, {"n": "s"}) == {"n": "s"}
    assert deep_merge({"n": "s"}, {"n": {"x": 1}}) == {"n": {"x": 1}}
    assert deep_merge({"t": ["a", "b"]}, {"t": ["c"]}) == {"t": ["c"]}


def test_deep_merge_does_not_mutate_either_side() -> None:
    """The inline mapping is a live Sphinx config value; merging must copy."""
    base = {"n": {"x": 1}}
    override = {"n": {"y": 2}}
    deep_merge(base, override)
    assert base == {"n": {"x": 1}}
    assert override == {"n": {"y": 2}}


@pytest.mark.parametrize(
    "data",
    [
        {"a": 1, "b": "s", "c": True, "d": 1.5},
        {"nested": {"deep": {"x": 1}}},
        {"empty_list": []},
        {"uniform": ["a", "b"]},
        {"empty_map": {}},
    ],
    ids=["scalars", "nested", "empty-list", "uniform-list", "empty-map"],
)
def test_valid_shapes_pass_validation(data: dict[str, Any]) -> None:
    validate_variant_data(data)


@pytest.mark.parametrize(
    ("data", "match"),
    [
        ({"a": {"b": None}}, "expected str/bool/int/float"),
        ({"a": [1, "x"]}, "arrays must be uniform type"),
        ({"a": [{"x": 1}]}, "array elements must be"),
        ({"a": (1, 2)}, "expected str/bool/int/float"),
        ({1: "x"}, "all keys must be strings"),
    ],
    ids=["none-leaf", "mixed-list", "list-of-maps", "tuple", "non-str-key"],
)
def test_invalid_shapes_are_rejected(data: dict[str, Any], match: str) -> None:
    """Every rejection names the dotted path, so a deep map is debuggable."""
    with pytest.raises(VariantDataError, match=match):
        validate_variant_data(data)


def test_validation_names_the_dotted_path() -> None:
    with pytest.raises(VariantDataError, match=r"var\.build\.opt"):
        validate_variant_data({"build": {"opt": None}})


def test_load_requires_a_json_object(tmp_path: Path) -> None:
    path = tmp_path / "vd.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(VariantDataError, match="must contain a JSON object"):
        load_variant_data_file(path)


def test_load_reports_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(VariantDataError, match="not found"):
        load_variant_data_file(tmp_path / "absent.json")


def test_load_reports_undecodable_json(tmp_path: Path) -> None:
    path = tmp_path / "vd.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(VariantDataError, match="invalid JSON"):
        load_variant_data_file(path)


def test_load_validates_the_loaded_shape(tmp_path: Path) -> None:
    """A file is held to the same shape rules as the inline table."""
    path = tmp_path / "vd.json"
    path.write_text(json.dumps({"a": [1, "x"]}), encoding="utf-8")
    with pytest.raises(VariantDataError, match="uniform"):
        load_variant_data_file(path)


def _write(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "vd.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_resolve_loads_the_file_first_and_merges_inline_on_top(
    tmp_path: Path,
) -> None:
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


def test_resolve_with_only_a_file(tmp_path: Path) -> None:
    """Nothing inline: the file is the whole map."""
    path = _write(tmp_path, {"edition": "base", "build": {"opt": 2}})
    assert resolve_variant_data(None, path) == {"edition": "base", "build": {"opt": 2}}


def test_resolve_with_only_inline() -> None:
    assert resolve_variant_data({"edition": "pro"}, None) == {"edition": "pro"}


def test_resolve_with_neither_side_is_the_empty_map() -> None:
    """A project with no variant data at all evaluates rules against ``{}``.

    Every ``var.*`` reference is then an unknown key, so every rule reports and
    excludes. That is the fail-closed direction, and it is what a rule set
    without its data should do.
    """
    assert resolve_variant_data(None, None) == {}


def test_resolve_rejects_a_malformed_inline_map() -> None:
    with pytest.raises(VariantDataError):
        resolve_variant_data({"a": [1, "x"]}, None)


def test_resolve_is_idempotent_over_an_already_merged_inline_map(
    tmp_path: Path,
) -> None:
    """The post-#1787 cell, at the function level.

    When sphinx-needs has already resolved, ``needs_variant_data`` holds the
    merged map and ``needs_variant_data_file`` still points at the file. Feeding
    both back in has to return the same map, or the two tools would disagree
    about which documents exist.
    """
    path = _write(tmp_path, {"edition": "base", "cpu": "arm", "build": {"opt": 2}})
    inline = {"edition": "pro", "build": {"debug": True}}
    once = resolve_variant_data(inline, path)
    twice = resolve_variant_data(once, path)
    assert twice == once
