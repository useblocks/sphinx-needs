"""Tests for the AST-based simple filter fast path in sphinx_needs.ubquery."""

from __future__ import annotations

import ast
from unittest.mock import Mock

import pytest

from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import (
    filter_single_need,
)
from sphinx_needs.need_item import NeedItem, NeedsContent
from sphinx_needs.ubquery import (
    _expr_to_predicate,
    _get_field,
    try_build_simple_predicate,
)


def _make_need(**core_overrides: object) -> NeedItem:
    """Create a minimal NeedItem for testing."""
    core_base = {
        "id": "REQ_001",
        "type": "requirement",
        "type_name": "Req",
        "type_prefix": "REQ_",
        "type_color": "#000000",
        "type_style": "node",
        "status": "open",
        "tags": ["safety", "important"],
        "constraints": (),
        "title": "Test Requirement",
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
    core_base.update(core_overrides)
    return NeedItem(
        core=core_base,
        extras={},
        links={},
        source=None,
        content=NeedsContent(content="", doctype=".rst"),
        parts=(),
    )


# --- _get_field tests ---


class TestGetField:
    def test_existing_field(self) -> None:
        need = _make_need()
        assert _get_field(need, "status") == "open"

    def test_missing_field(self) -> None:
        need = _make_need()
        with pytest.raises(NameError, match="name 'nonexistent' is not defined"):
            _get_field(need, "nonexistent")

    def test_field_with_none_value(self) -> None:
        need = _make_need(style=None)
        assert _get_field(need, "style") is None


# --- try_build_simple_predicate tests ---


@pytest.mark.parametrize(
    ("filter_string", "expected", "need_kw"),
    [
        pytest.param('status == "open"', True, {}, id="eq-true"),
        pytest.param('status != "closed"', True, {}, id="ne-true"),
        pytest.param('"open" == status', True, {}, id="reversed-eq-true"),
        pytest.param('"open" != status', False, {}, id="reversed-ne-false"),
        pytest.param('type in ["requirement", "spec"]', True, {}, id="field-in-list"),
        pytest.param('type in ("requirement", "spec")', True, {}, id="field-in-tuple"),
        pytest.param('type in {"requirement", "spec"}', True, {}, id="field-in-set"),
        pytest.param('"safety" in tags', True, {}, id="value-in-field-true"),
        pytest.param('"missing" in tags', False, {}, id="value-in-field-false"),
        pytest.param("status", True, {}, id="bare-name-truthy"),
        pytest.param("status", False, {"status": ""}, id="bare-name-falsy"),
        pytest.param('not status == "closed"', True, {}, id="not-expr"),
        pytest.param(
            'type == "requirement" and status == "open"', True, {}, id="and-true"
        ),
        pytest.param(
            'type == "requirement" and status == "closed"', False, {}, id="and-false"
        ),
        pytest.param(
            'type == "requirement" or type == "spec"', True, {}, id="or-first-true"
        ),
        pytest.param(
            'type == "spec" or type == "requirement"', True, {}, id="or-second-true"
        ),
        pytest.param('type == "spec" or type == "impl"', False, {}, id="or-false"),
        pytest.param(
            'type == "not-set" and unknown == "something"',
            False,
            {},
            id="and-unknown-field",
        ),
    ],
)
def test_predicate_eval(
    filter_string: str, expected: bool, need_kw: dict[str, object]
) -> None:
    pred = try_build_simple_predicate(filter_string)
    assert pred is not None
    assert pred(_make_need(**need_kw)) is expected


@pytest.mark.parametrize(
    "filter_string",
    [
        pytest.param('search("pattern", id)', id="function-call"),
        pytest.param("status===", id="syntax-error"),
    ],
)
def test_predicate_returns_none(filter_string: str) -> None:
    assert try_build_simple_predicate(filter_string) is None


def test_predicate_missing_field_raises() -> None:
    pred = try_build_simple_predicate('nonexistent == "value"')
    assert pred is not None
    with pytest.raises(NameError, match="'nonexistent'"):
        pred(_make_need())


def test_predicate_caching() -> None:
    pred1 = try_build_simple_predicate('status == "open"')
    pred2 = try_build_simple_predicate('status == "open"')
    assert pred1 is pred2


# --- _expr_to_predicate comparison operator tests ---


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        pytest.param('id < "ZZZ"', True, id="lt"),
        pytest.param('id <= "REQ_001"', True, id="le"),
        pytest.param('id > "AAA"', True, id="gt"),
        pytest.param('id >= "REQ_001"', True, id="ge"),
    ],
)
def test_expr_to_predicate_comparison(expr: str, expected: bool) -> None:
    tree = ast.parse(expr, mode="eval")
    pred = _expr_to_predicate(tree.body)
    assert pred is not None
    assert pred(_make_need()) is expected


# --- filter_single_need with simple_filter tests ---


class TestFilterSingleNeedSimpleFilter:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.need = _make_need()
        self.config = Mock()
        self.config.filter_data = {}

    @pytest.mark.parametrize(
        ("filter_string", "expected"),
        [
            pytest.param('status == "open"', True, id="eq-true"),
            pytest.param('status == "closed"', False, id="eq-false"),
            pytest.param(
                'type == "requirement" and status == "open"', True, id="and-true"
            ),
            pytest.param('"safety" in tags', True, id="value-in-tags"),
            pytest.param('not status == "closed"', True, id="not-expr"),
        ],
    )
    def test_simple_filter(self, filter_string: str, expected: bool) -> None:
        result = filter_single_need(
            self.need, self.config, filter_string, simple_filter=True
        )
        assert result is expected

    def test_complex_falls_through_to_eval(self) -> None:
        """Complex expressions fall through to eval() even with simple_filter=True."""
        result = filter_single_need(
            self.need,
            self.config,
            'type == "requirement" or [x for x in ["requirement"] if x == type][0] == type',
            simple_filter=True,
        )
        assert result is True

    def test_missing_field(self) -> None:
        """Missing field raises NeedsInvalidFilter, matching eval() behavior."""
        with pytest.raises(NeedsInvalidFilter, match="'nonexistent'"):
            filter_single_need(
                self.need,
                self.config,
                'nonexistent == "value"',
                simple_filter=True,
            )

    def test_false_does_not_use_fast_path(self) -> None:
        """When simple_filter is False (default), the eval path is used."""
        result = filter_single_need(self.need, self.config, 'status == "open"')
        assert result is True


# --- context-only name blocklist ---


@pytest.mark.parametrize(
    "filter_string",
    [
        pytest.param("needs", id="bare-needs"),
        pytest.param("current_need", id="bare-current_need"),
        pytest.param("search", id="bare-search"),
        pytest.param("c", id="bare-c"),
        pytest.param('current_need == "REQ_001"', id="comparison"),
        pytest.param('"REQ_001" == current_need', id="reversed-comparison"),
        pytest.param('current_need in ["REQ_001", "REQ_002"]', id="in-list"),
        pytest.param('"x" in needs', id="value-in-context-name"),
        pytest.param('status == "open" and needs', id="and-with-context"),
        pytest.param('status == "open" or needs', id="or-with-context"),
        pytest.param("not needs", id="not-context"),
    ],
)
def test_context_only_name_returns_none(filter_string: str) -> None:
    assert try_build_simple_predicate(filter_string) is None


def test_context_only_normal_field_still_works() -> None:
    """Sanity check: non-blocked names still produce predicates."""
    pred = try_build_simple_predicate('status == "open"')
    assert pred is not None
    assert pred(_make_need()) is True


# --- filter_data fallback ---


class TestFilterDataFallback:
    """Tests for filter_data support in the fast path."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.need = _make_need()

    def test_predicate_resolves_filter_data_key(self) -> None:
        pred = try_build_simple_predicate('project == "alpha"')
        assert pred is not None
        with pytest.raises(NameError):
            pred(self.need, None)
        assert pred(self.need, {"project": "alpha"}) is True
        assert pred(self.need, {"project": "beta"}) is False

    def test_filter_data_shadows_need_field(self) -> None:
        """filter_data values take precedence over need fields (matches slow path)."""
        pred = try_build_simple_predicate('status == "override"')
        assert pred is not None
        assert pred(self.need, {"status": "override"}) is True
        assert pred(self.need, None) is False

    def test_filter_single_need_passes_filter_data(self) -> None:
        """filter_single_need with simple_filter=True passes config.filter_data."""
        config = Mock()
        config.filter_data = {"project": "alpha"}
        result = filter_single_need(
            self.need, config, 'project == "alpha"', simple_filter=True
        )
        assert result is True

    def test_filter_single_need_filter_data_shadows(self) -> None:
        """filter_data shadows need fields in the fast path (matches slow path)."""
        config = Mock()
        config.filter_data = {"status": "override"}
        result = filter_single_need(
            self.need, config, 'status == "override"', simple_filter=True
        )
        assert result is True

    def test_empty_filter_data_no_effect(self) -> None:
        """Empty filter_data behaves like no filter_data."""
        config = Mock()
        config.filter_data = {}
        result = filter_single_need(
            self.need, config, 'status == "open"', simple_filter=True
        )
        assert result is True

    def test_filter_data_in_compound_expr(self) -> None:
        """filter_data works in compound (and/or) expressions."""
        pred = try_build_simple_predicate('status == "open" and project == "alpha"')
        assert pred is not None
        assert pred(self.need, {"project": "alpha"}) is True
        assert pred(self.need, {"project": "beta"}) is False
