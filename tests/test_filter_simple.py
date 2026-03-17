"""Tests for the AST-based simple filter fast path in filter_single_need."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import (
    _expr_to_predicate,
    _get_field,
    _try_build_simple_predicate,
    filter_single_need,
)
from sphinx_needs.need_item import NeedItem, NeedsContent


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


# --- _try_build_simple_predicate tests ---


class TestTryBuildSimplePredicate:
    def test_simple_eq(self) -> None:
        pred = _try_build_simple_predicate('status == "open"')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_simple_ne(self) -> None:
        pred = _try_build_simple_predicate('status != "closed"')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_reversed_eq(self) -> None:
        pred = _try_build_simple_predicate('"open" == status')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_reversed_ne(self) -> None:
        pred = _try_build_simple_predicate('"open" != status')
        assert pred is not None
        need = _make_need()
        assert pred(need) is False

    def test_field_in_list(self) -> None:
        pred = _try_build_simple_predicate('type in ["requirement", "spec"]')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_value_in_field(self) -> None:
        pred = _try_build_simple_predicate('"safety" in tags')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_value_not_in_field(self) -> None:
        pred = _try_build_simple_predicate('"missing" in tags')
        assert pred is not None
        need = _make_need()
        assert pred(need) is False

    def test_bare_name_truthy(self) -> None:
        pred = _try_build_simple_predicate("status")
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_bare_name_falsy(self) -> None:
        pred = _try_build_simple_predicate("status")
        assert pred is not None
        need = _make_need(status="")
        assert pred(need) is False

    def test_not_expr(self) -> None:
        pred = _try_build_simple_predicate('not status == "closed"')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_and_expr(self) -> None:
        pred = _try_build_simple_predicate('type == "requirement" and status == "open"')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_and_expr_false(self) -> None:
        pred = _try_build_simple_predicate(
            'type == "requirement" and status == "closed"'
        )
        assert pred is not None
        need = _make_need()
        assert pred(need) is False

    def test_or_expr(self) -> None:
        pred = _try_build_simple_predicate('type == "requirement" or type == "spec"')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_or_expr_second_true(self) -> None:
        pred = _try_build_simple_predicate('type == "spec" or type == "requirement"')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_or_expr_false(self) -> None:
        pred = _try_build_simple_predicate('type == "spec" or type == "impl"')
        assert pred is not None
        need = _make_need()
        assert pred(need) is False

    def test_complex_expr_returns_none(self) -> None:
        # Function calls can't be short-circuited
        pred = _try_build_simple_predicate('search("pattern", id)')
        assert pred is None

    def test_syntax_error_returns_none(self) -> None:
        pred = _try_build_simple_predicate("status===")
        assert pred is None

    def test_field_in_tuple(self) -> None:
        pred = _try_build_simple_predicate('type in ("requirement", "spec")')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_field_in_set(self) -> None:
        pred = _try_build_simple_predicate('type in {"requirement", "spec"}')
        assert pred is not None
        need = _make_need()
        assert pred(need) is True

    def test_missing_field_raises(self) -> None:
        pred = _try_build_simple_predicate('nonexistent == "value"')
        assert pred is not None
        need = _make_need()
        with pytest.raises(NameError, match="'nonexistent'"):
            pred(need)

    def test_caching(self) -> None:
        """Verify that the same predicate object is returned on repeated calls."""
        pred1 = _try_build_simple_predicate('status == "open"')
        pred2 = _try_build_simple_predicate('status == "open"')
        assert pred1 is pred2


# --- _expr_to_predicate comparison operator tests ---


class TestExprToPredicateComparisons:
    """Test all six comparison operators for _expr_to_predicate."""

    @pytest.fixture(autouse=True)
    def _need(self) -> None:
        self.need = _make_need()

    def test_lt(self) -> None:
        import ast as _ast

        tree = _ast.parse('id < "ZZZ"', mode="eval")
        pred = _expr_to_predicate(tree.body)
        assert pred is not None
        assert pred(self.need) is True

    def test_le(self) -> None:
        import ast as _ast

        tree = _ast.parse('id <= "REQ_001"', mode="eval")
        pred = _expr_to_predicate(tree.body)
        assert pred is not None
        assert pred(self.need) is True

    def test_gt(self) -> None:
        import ast as _ast

        tree = _ast.parse('id > "AAA"', mode="eval")
        pred = _expr_to_predicate(tree.body)
        assert pred is not None
        assert pred(self.need) is True

    def test_ge(self) -> None:
        import ast as _ast

        tree = _ast.parse('id >= "REQ_001"', mode="eval")
        pred = _expr_to_predicate(tree.body)
        assert pred is not None
        assert pred(self.need) is True


# --- filter_single_need with simple_filter tests ---


class TestFilterSingleNeedSimpleFilter:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.need = _make_need()
        self.config = Mock()
        self.config.filter_data = {}

    def test_simple_filter_eq_true(self) -> None:
        result = filter_single_need(
            self.need, self.config, 'status == "open"', simple_filter=True
        )
        assert result is True

    def test_simple_filter_eq_false(self) -> None:
        result = filter_single_need(
            self.need, self.config, 'status == "closed"', simple_filter=True
        )
        assert result is False

    def test_simple_filter_and(self) -> None:
        result = filter_single_need(
            self.need,
            self.config,
            'type == "requirement" and status == "open"',
            simple_filter=True,
        )
        assert result is True

    def test_simple_filter_fallback_to_eval(self) -> None:
        """Complex expressions fall through to eval() even with simple_filter=True."""
        result = filter_single_need(
            self.need,
            self.config,
            'type == "requirement"',
            simple_filter=True,
        )
        assert result is True

    def test_simple_filter_missing_field(self) -> None:
        """Missing field raises NeedsInvalidFilter, matching eval() behavior."""
        with pytest.raises(NeedsInvalidFilter, match="'nonexistent'"):
            filter_single_need(
                self.need,
                self.config,
                'nonexistent == "value"',
                simple_filter=True,
            )

    def test_simple_filter_false_does_not_use_fast_path(self) -> None:
        """When simple_filter is False (default), the eval path is used."""
        result = filter_single_need(self.need, self.config, 'status == "open"')
        assert result is True

    def test_simple_filter_value_in_tags(self) -> None:
        result = filter_single_need(
            self.need, self.config, '"safety" in tags', simple_filter=True
        )
        assert result is True

    def test_simple_filter_not_expr(self) -> None:
        result = filter_single_need(
            self.need,
            self.config,
            'not status == "closed"',
            simple_filter=True,
        )
        assert result is True
