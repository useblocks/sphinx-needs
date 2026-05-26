"""Tests for variant data feature."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sphinx_needs.variant_data import (
    VariantDataError,
    VariantDataProxy,
    deep_merge,
    load_variant_data_file,
    resolve_variant_data,
    validate_variant_data,
)


class TestVariantDataProxy:
    """Tests for VariantDataProxy."""

    def test_basic_access(self) -> None:
        proxy = VariantDataProxy({"cpu": "arm", "os": "linux"})
        assert proxy.cpu == "arm"
        assert proxy.os == "linux"

    def test_nested_access(self) -> None:
        proxy = VariantDataProxy({"build": {"debug": True, "opt_level": 2}})
        assert proxy.build.debug is True
        assert proxy.build.opt_level == 2

    def test_missing_key_raises(self) -> None:
        proxy = VariantDataProxy({"cpu": "arm"})
        with pytest.raises(AttributeError, match=r"Unknown variant key: var\.missing"):
            proxy.missing  # noqa: B018

    def test_nested_missing_key(self) -> None:
        proxy = VariantDataProxy({"build": {"debug": True}})
        with pytest.raises(AttributeError, match="Unknown variant key"):
            proxy.build.release  # noqa: B018

    def test_contains(self) -> None:
        proxy = VariantDataProxy({"cpu": "arm"})
        assert "cpu" in proxy
        assert "gpu" not in proxy

    def test_iter(self) -> None:
        proxy = VariantDataProxy({"a": 1, "b": 2})
        assert set(proxy) == {"a", "b"}

    def test_repr(self) -> None:
        proxy = VariantDataProxy({"x": 1}, path=("var",))
        assert "var" in repr(proxy)

    def test_immutable(self) -> None:
        proxy = VariantDataProxy({"x": 1})
        with pytest.raises(AttributeError):
            proxy.x = 2  # type: ignore[misc]

    def test_list_values(self) -> None:
        proxy = VariantDataProxy({"archs": ["arm", "x86"]})
        assert proxy.archs == ["arm", "x86"]
        assert "arm" in proxy.archs


class TestValidateVariantData:
    """Tests for validate_variant_data."""

    def test_valid_data(self) -> None:
        validate_variant_data({"cpu": "arm", "nested": {"key": "val"}})

    def test_non_dict_raises(self) -> None:
        with pytest.raises(VariantDataError):
            validate_variant_data("not a dict")  # type: ignore[arg-type]

    def test_non_string_key_raises(self) -> None:
        with pytest.raises(VariantDataError):
            validate_variant_data({123: "val"})  # type: ignore[dict-item]

    def test_bool_int_array_not_mixed(self) -> None:
        """bool and int must not be conflated in arrays (bool is subclass of int)."""
        with pytest.raises(VariantDataError, match=r"expected int.*got bool"):
            validate_variant_data({"vals": [1, True, 2]})
        with pytest.raises(VariantDataError, match=r"expected bool.*got int"):
            validate_variant_data({"vals": [True, 1, False]})

    def test_none_value_raises(self) -> None:
        with pytest.raises(VariantDataError, match="got NoneType"):
            validate_variant_data({"x": None})


class TestDeepMerge:
    """Tests for deep_merge."""

    def test_simple_merge(self) -> None:
        assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_override(self) -> None:
        assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_nested_merge(self) -> None:
        base = {"build": {"debug": True, "opt": 1}}
        override = {"build": {"opt": 2}}
        result = deep_merge(base, override)
        assert result == {"build": {"debug": True, "opt": 2}}


class TestLoadVariantDataFile:
    """Tests for load_variant_data_file."""

    def test_load_json(self, tmp_path: Path) -> None:
        data = {"cpu": "arm", "nested": {"key": "val"}}
        f = tmp_path / "data.json"
        f.write_text(json.dumps(data))
        result = load_variant_data_file(str(f))
        assert result == data

    def test_missing_file_raises(self) -> None:
        with pytest.raises(VariantDataError, match="not found"):
            load_variant_data_file("/nonexistent/path.json")

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("{invalid")
        with pytest.raises(VariantDataError):
            load_variant_data_file(str(f))


class TestResolveVariantData:
    """Tests for resolve_variant_data."""

    def test_inline_only(self) -> None:
        result = resolve_variant_data({"cpu": "arm"}, None)
        assert result == {"cpu": "arm"}

    def test_file_only(self, tmp_path: Path) -> None:
        data = {"os": "linux"}
        f = tmp_path / "v.json"
        f.write_text(json.dumps(data))
        result = resolve_variant_data({}, str(f))
        assert result == {"os": "linux"}

    def test_file_overrides_inline(self, tmp_path: Path) -> None:
        f = tmp_path / "v.json"
        f.write_text(json.dumps({"cpu": "x86", "extra": True}))
        result = resolve_variant_data({"cpu": "arm"}, str(f))
        # inline merges on top of file, so inline wins
        assert result["cpu"] == "arm"
        assert result["extra"] is True
