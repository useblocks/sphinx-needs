"""Tests for variant data feature."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sphinx_needs.ubquery import try_build_simple_predicate
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
        proxy = VariantDataProxy({"x": 1}, path="var")
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


class TestUbqueryFastPath:
    """Tests for fast-path compilation of var.* expressions."""

    def _make_ctx(self, data: dict) -> dict:
        return {"var": VariantDataProxy(data)}

    def test_var_eq(self) -> None:
        pred = try_build_simple_predicate('var.cpu == "arm"')
        assert pred is not None
        ctx = self._make_ctx({"cpu": "arm"})
        assert pred({}, ctx) is True
        ctx2 = self._make_ctx({"cpu": "x86"})
        assert pred({}, ctx2) is False

    def test_var_ne(self) -> None:
        pred = try_build_simple_predicate('var.cpu != "arm"')
        assert pred is not None
        assert pred({}, self._make_ctx({"cpu": "x86"})) is True

    def test_var_nested(self) -> None:
        pred = try_build_simple_predicate("var.build.debug == True")
        assert pred is not None
        ctx = self._make_ctx({"build": {"debug": True}})
        assert pred({}, ctx) is True

    def test_value_in_var(self) -> None:
        pred = try_build_simple_predicate('"arm" in var.archs')
        assert pred is not None
        ctx = self._make_ctx({"archs": ["arm", "x86"]})
        assert pred({}, ctx) is True

    def test_value_not_in_var(self) -> None:
        pred = try_build_simple_predicate('"mips" not in var.archs')
        assert pred is not None
        ctx = self._make_ctx({"archs": ["arm", "x86"]})
        assert pred({}, ctx) is True

    def test_swapped_comparison(self) -> None:
        pred = try_build_simple_predicate('"arm" == var.cpu')
        assert pred is not None
        assert pred({}, self._make_ctx({"cpu": "arm"})) is True

    def test_bare_var_bails(self) -> None:
        """Bare 'var' as a name should bail to slow path (return None)."""
        pred = try_build_simple_predicate("var")
        assert pred is None
