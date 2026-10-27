"""Tests for the AST-based simple filter fast path in sphinx_needs.ubquery."""

from __future__ import annotations

import ast
from unittest.mock import Mock, patch

import pytest

from sphinx_needs import filter_common
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import (
    filter_single_need,
)
from sphinx_needs.need_item import NeedItem, NeedItemSourceDirective, NeedsContent
from sphinx_needs.ubquery import (
    ORIGIN_KEY,
    CompiledFilter,
    _expr_to_predicate,
    _get_field,
    compile_portable,
    try_build_simple_predicate,
)


def _make_need(
    *, extras: dict[str, object] | None = None, **core_overrides: object
) -> NeedItem:
    """Create a minimal NeedItem for testing, written in the document ``index``."""
    core_base = {
        "id": "REQ_001",
        "type": "requirement",
        "type_name": "Req",
        "type_prefix": "REQ_",
        "type_ancestors": ["requirement"],
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
        extras=dict(extras or {}),
        links={},
        source=NeedItemSourceDirective(docname="index", lineno=1, lineno_content=2),
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
        pytest.param(
            'type not in ["spec", "impl"]', True, {}, id="field-not-in-list-true"
        ),
        pytest.param(
            'type not in ["requirement", "spec"]',
            False,
            {},
            id="field-not-in-list-false",
        ),
        pytest.param('"missing" not in tags', True, {}, id="value-not-in-field-true"),
        pytest.param('"safety" not in tags', False, {}, id="value-not-in-field-false"),
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
        pytest.param('search("REQ", id)', True, {}, id="search-match"),
        pytest.param('search("MISSING", id)', False, {}, id="search-no-match"),
        pytest.param(
            'search("REQ", id) and status == "open"',
            True,
            {},
            id="search-and-compare",
        ),
        pytest.param(r'search("^\w+_\d+$", id)', True, {}, id="search-regex"),
        pytest.param('not search("MISSING", id)', True, {}, id="not-search"),
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
        pytest.param("status===", id="syntax-error"),
        pytest.param("search(variable, id)", id="search-non-literal-pattern"),
        pytest.param('search("pattern")', id="search-one-arg"),
        pytest.param('search("a", "b")', id="search-two-literals"),
        pytest.param('search("a", id, "c")', id="search-three-args"),
        pytest.param('search("a", id, extra=1)', id="search-with-kwarg"),
    ],
)
def test_predicate_returns_none(filter_string: str) -> None:
    assert try_build_simple_predicate(filter_string) is None


def test_search_missing_field_raises() -> None:
    pred = try_build_simple_predicate('search("pattern", nonexistent)')
    assert pred is not None
    with pytest.raises(NameError, match="'nonexistent'"):
        pred(_make_need())


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


# --- filter_single_need fast-path tests ---


class TestFilterSingleNeedFastPath:
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
            pytest.param(
                'search("REQ", id) and status == "open"',
                True,
                id="search-and-compare",
            ),
        ],
    )
    def test_simple_filter(self, filter_string: str, expected: bool) -> None:
        result = filter_single_need(self.need, self.config, filter_string)
        assert result is expected

    def test_complex_falls_through_to_eval(self) -> None:
        """Complex expressions fall through to eval()."""
        result = filter_single_need(
            self.need,
            self.config,
            'type == "requirement" or [x for x in ["requirement"] if x == type][0] == type',
        )
        assert result is True

    def test_missing_field(self) -> None:
        """Missing field raises NeedsInvalidFilter, matching eval() behavior."""
        with pytest.raises(NeedsInvalidFilter, match="'nonexistent'"):
            filter_single_need(
                self.need,
                self.config,
                'nonexistent == "value"',
            )


# --- context-only name blocklist ---


@pytest.mark.parametrize(
    "filter_string",
    [
        pytest.param("needs", id="bare-needs"),
        pytest.param("current_need", id="bare-current_need"),
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
        """filter_single_need passes config.filter_data to the fast path."""
        config = Mock()
        config.filter_data = {"project": "alpha"}
        result = filter_single_need(self.need, config, 'project == "alpha"')
        assert result is True

    def test_filter_single_need_filter_data_shadows(self) -> None:
        """filter_data shadows need fields in the fast path (matches slow path)."""
        config = Mock()
        config.filter_data = {"status": "override"}
        result = filter_single_need(self.need, config, 'status == "override"')
        assert result is True

    def test_empty_filter_data_no_effect(self) -> None:
        """Empty filter_data behaves like no filter_data."""
        config = Mock()
        config.filter_data = {}
        result = filter_single_need(self.need, config, 'status == "open"')
        assert result is True

    def test_filter_data_in_compound_expr(self) -> None:
        """filter_data works in compound (and/or) expressions."""
        pred = try_build_simple_predicate('status == "open" and project == "alpha"')
        assert pred is not None
        assert pred(self.need, {"project": "alpha"}) is True
        assert pred(self.need, {"project": "beta"}) is False


# --- variant data (var.*) fast-path tests ---


class TestVariantDataFastPath:
    """Tests for var.* attribute chain support in the fast path."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from sphinx_needs.variant_data import VariantDataProxy

        self.need = _make_need()
        self.ctx = {
            "var": VariantDataProxy(
                {
                    "cpu": "arm",
                    "os": "linux",
                    "build": {"debug": True, "opt_level": 2},
                    "archs": ["arm", "x86"],
                }
            )
        }

    @pytest.mark.parametrize(
        ("filter_string", "expected"),
        [
            pytest.param('var.cpu == "arm"', True, id="eq-true"),
            pytest.param('var.cpu == "x86"', False, id="eq-false"),
            pytest.param('var.cpu != "x86"', True, id="ne-true"),
            pytest.param('var.cpu != "arm"', False, id="ne-false"),
            pytest.param('"arm" == var.cpu', True, id="swapped-eq-true"),
            pytest.param('"x86" == var.cpu', False, id="swapped-eq-false"),
            pytest.param('var.os == "linux"', True, id="eq-os"),
        ],
        ids=lambda x: "",
    )
    def test_simple_comparison(self, filter_string: str, expected: bool) -> None:
        pred = try_build_simple_predicate(filter_string)
        assert pred is not None
        assert pred(self.need, self.ctx) is expected

    @pytest.mark.parametrize(
        ("filter_string", "expected"),
        [
            pytest.param("var.build.debug == True", True, id="nested-bool-true"),
            pytest.param("var.build.debug == False", False, id="nested-bool-false"),
            pytest.param("var.build.opt_level == 2", True, id="nested-int"),
            pytest.param("var.build.opt_level == 3", False, id="nested-int-false"),
        ],
        ids=lambda x: "",
    )
    def test_nested_comparison(self, filter_string: str, expected: bool) -> None:
        pred = try_build_simple_predicate(filter_string)
        assert pred is not None
        assert pred(self.need, self.ctx) is expected

    @pytest.mark.parametrize(
        ("filter_string", "expected"),
        [
            pytest.param('"arm" in var.archs', True, id="in-true"),
            pytest.param('"mips" in var.archs', False, id="in-false"),
            pytest.param('"mips" not in var.archs', True, id="not-in-true"),
            pytest.param('"arm" not in var.archs', False, id="not-in-false"),
        ],
        ids=lambda x: "",
    )
    def test_membership(self, filter_string: str, expected: bool) -> None:
        pred = try_build_simple_predicate(filter_string)
        assert pred is not None
        assert pred(self.need, self.ctx) is expected

    def test_compound_var_and_field(self) -> None:
        """var.* works combined with need field comparisons."""
        pred = try_build_simple_predicate('var.cpu == "arm" and status == "open"')
        assert pred is not None
        assert pred(self.need, self.ctx) is True

        pred2 = try_build_simple_predicate('var.cpu == "x86" and status == "open"')
        assert pred2 is not None
        assert pred2(self.need, self.ctx) is False

    def test_compound_var_or(self) -> None:
        pred = try_build_simple_predicate('var.cpu == "x86" or var.os == "linux"')
        assert pred is not None
        assert pred(self.need, self.ctx) is True

    def test_not_var(self) -> None:
        pred = try_build_simple_predicate('not var.cpu == "x86"')
        assert pred is not None
        assert pred(self.need, self.ctx) is True

    def test_bare_var_returns_none(self) -> None:
        """Bare 'var' name should bail to slow path (return None)."""
        assert try_build_simple_predicate("var") is None

    def test_var_in_comparison_returns_none_for_non_var_root(self) -> None:
        """Attribute chains not rooted in 'var' bail to slow path."""
        assert try_build_simple_predicate('foo.bar == "x"') is None

    def test_missing_var_key_raises(self) -> None:
        """Accessing a missing key on var raises AttributeError at eval time."""
        pred = try_build_simple_predicate('var.missing == "x"')
        assert pred is not None
        with pytest.raises(AttributeError):
            pred(self.need, self.ctx)

    def test_no_ctx_raises(self) -> None:
        """If ctx is None, accessing var raises NameError."""
        pred = try_build_simple_predicate('var.cpu == "arm"')
        assert pred is not None
        with pytest.raises(NameError):
            pred(self.need, None)

    def test_filter_single_need_with_variant_data(self) -> None:
        """filter_single_need passes variant data through to the fast path."""
        from sphinx_needs.variant_data import VariantDataProxy

        config = Mock()
        config.filter_data = {}
        config.variant_data = {"cpu": "arm"}
        config.variant_data_proxy = VariantDataProxy(config.variant_data)
        result = filter_single_need(self.need, config, 'var.cpu == "arm"')
        assert result is True


# --- the portable grammar: the forms added to the fast path ---


@pytest.mark.parametrize(
    ("filter_string", "expected", "extras"),
    [
        # `is_null_expr` / `is_not_null_expr`
        pytest.param("style is None", True, {}, id="is-none"),
        pytest.param("status is None", False, {}, id="is-none-false"),
        pytest.param("status is not None", True, {}, id="is-not-none"),
        # `var_field_with_len`, either side of a comparison
        pytest.param("len(tags) > 1", True, {}, id="len-gt"),
        pytest.param("len(tags) == 0", False, {}, id="len-eq"),
        pytest.param("0 < len(tags)", True, {}, id="number-lt-len"),
        pytest.param("len(title) >= -1", True, {}, id="len-negative-number"),
        pytest.param("len(tags)", True, {}, id="bare-len"),
        # `var_field_with_lower` / `var_field_with_upper`
        pytest.param('status.upper() == "OPEN"', True, {}, id="upper-eq"),
        pytest.param('"open" == status.lower()', True, {}, id="literal-eq-lower"),
        pytest.param('"test" in title.lower()', True, {}, id="literal-in-lower"),
        pytest.param(
            '"test" not in title.upper()', True, {}, id="literal-not-in-upper"
        ),
        pytest.param(
            'status.upper() in ["OPEN", "DONE"]', True, {}, id="upper-in-list"
        ),
        # `str_predicate_method`, composable with the chains
        pytest.param('id.startswith("REQ")', True, {}, id="startswith"),
        pytest.param('id.endswith("001")', True, {}, id="endswith"),
        pytest.param('id.lower().startswith("req")', True, {}, id="lower-startswith"),
        pytest.param('title.upper().endswith("MENT")', True, {}, id="upper-endswith"),
        pytest.param('not id.startswith("SPEC")', True, {}, id="not-startswith"),
        # `comparison_expr` with an operand on both sides
        pytest.param(
            "owner == lead", True, {"owner": "a", "lead": "a"}, id="name-eq-name"
        ),
        pytest.param(
            "owner != lead", True, {"owner": "a", "lead": "b"}, id="name-ne-name"
        ),
        pytest.param(
            "effort < budget", True, {"effort": 1, "budget": 2}, id="name-lt-name"
        ),
        pytest.param("len(tags) == len(title)", False, {}, id="len-eq-len"),
        pytest.param("status.lower() == status", True, {}, id="lower-eq-name"),
        # `search_check` over any operand
        pytest.param('search("^test", title.lower())', True, {}, id="search-lower"),
        # `bool_literal_expr`
        pytest.param("True", True, {}, id="bare-true"),
        pytest.param("False or status", True, {}, id="false-or"),
        pytest.param("not True", False, {}, id="not-true"),
        # `in_list_expr` with a negative number literal
        pytest.param(
            "effort in [-1, 0]", True, {"effort": -1}, id="in-negative-number"
        ),
    ],
)
def test_portable_form_compiles_and_answers(
    filter_string: str, expected: bool, extras: dict[str, object]
) -> None:
    pred = try_build_simple_predicate(filter_string)
    assert pred is not None, compile_portable(filter_string).rejection
    assert pred(_make_need(extras=extras), None) is expected


@pytest.mark.parametrize(
    ("filter_string", "reason"),
    [
        # outside the grammar: the construct the debug report names
        pytest.param("sphinx_tag in tags", "compare:name-in-name", id="name-in-name"),
        pytest.param("x in y.lower()", "compare:name-in-name", id="name-in-lower"),
        pytest.param("x == [1]", "compare:list", id="list-beside-eq"),
        pytest.param("[] != x", "compare:list", id="list-beside-ne"),
        pytest.param('x.lower() < "a"', "compare:ordering", id="ordering-string"),
        pytest.param("len(x) > True", "compare:ordering", id="ordering-bool"),
        pytest.param("None is x", "compare:is", id="none-is"),
        pytest.param("x is True", "compare:is", id="is-true"),
        pytest.param("1 < x < 3", "compare:chained", id="chained"),
        pytest.param('"a" in [x]', "compare:in", id="literal-in-list-of-names"),
        pytest.param('x.lower() in ("a",)', "tuple", id="tuple-after-function"),
        pytest.param("len(x.lower())", "call:len", id="len-of-function"),
        pytest.param("x.lower().upper()", "method:upper", id="chained-functions"),
        pytest.param("x.strip()", "method:strip", id="other-method"),
        pytest.param("x.startswith(y)", "method:startswith", id="startswith-name"),
        pytest.param(
            'x.startswith("a", 1)', "method:startswith", id="startswith-2-args"
        ),
        pytest.param("bool(arch)", "call:bool", id="other-function"),
        pytest.param("any(tags)", "call:any", id="any"),
        pytest.param("c.this_doc() == True", "call:c.this_doc", id="this-doc-compared"),
        pytest.param('c.in_namespace("x")', "call:c.in_namespace", id="c-other"),
        pytest.param('id.ns == "x"', "attribute:id", id="facet-root"),
        pytest.param("needs", "name:needs", id="needs"),
        pytest.param("x[0] == 1", "subscript", id="subscript"),
        pytest.param("[t for t in tags]", "comprehension", id="comprehension"),
        pytest.param("x + 1 > 2", "arithmetic", id="arithmetic"),
        pytest.param("1", "literal", id="bare-number"),
        pytest.param('"a" == "b"', "literal", id="literal-eq-literal"),
        pytest.param('f"{x}" == "a"', "fstring", id="fstring"),
        pytest.param("x if y else z", "ifexp", id="conditional"),
        pytest.param("(not status) == True", "not", id="not-as-an-operand"),
        pytest.param('search("(", title)', "call:search", id="search-bad-pattern"),
        pytest.param("status===", "syntax", id="syntax"),
    ],
)
def test_outside_the_grammar_names_its_construct(
    filter_string: str, reason: str
) -> None:
    compiled = compile_portable(filter_string)
    assert compiled.predicate is None
    assert compiled.rejection == reason


@pytest.mark.parametrize(
    "filter_string",
    [
        # accepted before the portable grammar was the reference; outside it
        pytest.param('id < "ZZZ"', id="name-ordering-string"),
        pytest.param('type in ("requirement", "spec")', id="name-in-tuple"),
        pytest.param('type in {"requirement", "spec"}', id="name-in-set"),
        pytest.param('status == b"open"', id="name-eq-bytes"),
    ],
)
def test_forms_accepted_before_the_grammar_stay(filter_string: str) -> None:
    assert try_build_simple_predicate(filter_string) is not None


@pytest.mark.parametrize(
    ("filter_string", "expected"),
    [
        # a list value against a list literal compares item by item, as eval's list does
        pytest.param('tags in ["safety"]', False, id="in-list"),
        pytest.param('tags not in ["safety"]', True, id="not-in-list"),
        pytest.param('tags in ("safety",)', False, id="in-tuple"),
    ],
)
def test_an_unhashable_value_in_a_list_answers_as_eval(
    filter_string: str, expected: bool
) -> None:
    config = Mock()
    config.filter_data = {}
    need = _make_need()
    assert filter_single_need(need, config, filter_string) is expected
    assert filter_single_need(need, config, f"({filter_string}) is True") is expected


def test_an_unhashable_value_in_a_set_fails_as_in_eval() -> None:
    config = Mock()
    config.filter_data = {}
    with pytest.raises(NeedsInvalidFilter, match="unhashable type: 'list'"):
        filter_single_need(_make_need(), config, 'tags in {"safety"}')
    with pytest.raises(NeedsInvalidFilter, match="unhashable type: 'list'"):
        filter_single_need(_make_need(), config, '(tags in {"safety"}) is True')


class TestThisDoc:
    """``c.this_doc()`` takes the document from the call, never from the compiled form."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.need = _make_need()
        self.config = Mock()
        self.config.filter_data = {}

    def test_compiled_once_for_every_document(self) -> None:
        compiled = compile_portable("c.this_doc()")
        assert compiled.predicate is not None
        assert compiled.reads_origin

    @pytest.mark.parametrize(
        ("origin", "expected"), [("index", True), ("other", False)]
    )
    def test_compares_the_document_of_the_call(
        self, origin: str, expected: bool
    ) -> None:
        result = filter_single_need(
            self.need, self.config, "c.this_doc()", origin_docname=origin
        )
        assert result is expected

    def test_without_a_document_raises_as_eval(self) -> None:
        for filter_string in ("c.this_doc()", "(c.this_doc()) is True"):
            with pytest.raises(
                NeedsInvalidFilter, match="`this_doc` can not be used in this context"
            ):
                filter_single_need(self.need, self.config, filter_string)


def test_a_builtin_name_reads_as_in_eval() -> None:
    """A name no field defines that is a Python builtin is the builtin, as eval reads it:
    as an operand it is compared. Alone it stays undefined in the parsed tier, which has
    no builtins, so the need is excluded and the filter reported; eval reads the builtin
    for its truth, as it reads every value (#1773), and a function is true."""
    config = Mock()
    config.filter_data = {}
    need = _make_need()
    for filter_string in ("status != filter", "(status != filter) is True"):
        assert filter_single_need(need, config, filter_string) is True
    assert compile_portable("filter").predicate is not None
    with pytest.raises(NeedsInvalidFilter, match="name 'filter' is not defined"):
        filter_single_need(need, config, "filter")
    assert compile_portable("filter if True else False").predicate is None
    assert filter_single_need(need, config, "filter if True else False") is True


class _AnswersWithAString(str):
    """A string whose ``startswith`` answers with a string, as a user's own value may."""

    def startswith(self, *args: object, **kwargs: object) -> str:
        return "yes" if super().startswith(*args, **kwargs) else ""


@pytest.mark.parametrize(("prefix", "expected"), [("a", True), ("b", False)])
def test_a_value_that_is_no_boolean_is_read_for_its_truth(
    prefix: str, expected: bool
) -> None:
    """Every tier reads a filter's value for its truth, the parsed one too, where a
    value's own method gives no boolean (#1773)."""
    config = Mock()
    config.filter_data = {}
    config.variant_data_proxy = None
    need = _make_need(extras={"owner": _AnswersWithAString("alice")})
    filter_string = f'owner.startswith("{prefix}")'
    assert compile_portable(filter_string).predicate is not None
    assert filter_single_need(need, config, filter_string) is expected
    assert filter_common.filter_needs_and_parts([need], config, filter_string) == (
        [need] if expected else []
    )
    refused = CompiledFilter(None, "refused", False)
    with patch.object(filter_common, "compile_portable", lambda _: refused):
        assert filter_single_need(need, config, filter_string) is expected


class _RefusesToAnswer(str):
    """A string whose ``startswith`` raises the error a failed filter raises."""

    def startswith(self, *args: object, **kwargs: object) -> bool:
        raise NeedsInvalidFilter("this value refuses to answer")


def test_a_value_that_fails_the_parsed_tier_is_reported_once() -> None:
    """In the parsed tier's loop, a need whose value fails the filter is excluded and
    the filter reported once, as in the eval loop, whatever the error: the other needs
    are still answered, and nothing ends the build (#2360)."""
    config = Mock()
    config.filter_data = {}
    config.variant_data_proxy = None
    failing = [
        _make_need(id=f"REQ_00{i}", extras={"owner": _RefusesToAnswer("alice")})
        for i in (1, 2)
    ]
    plain = _make_need(id="REQ_003", extras={"owner": "alice"})
    filter_string = 'owner.startswith("a")'
    assert compile_portable(filter_string).predicate is not None
    with patch.object(filter_common, "log_warning") as warn:
        found = filter_common.filter_needs_and_parts(
            [*failing, plain], config, filter_string
        )
    assert found == [plain]
    assert warn.call_count == 1
    _, message, code = warn.call_args.args
    assert code == "filter"
    assert message == (
        f"Filter {filter_string!r} not valid. Error: this value refuses to answer."
    )


def _outcome(need: NeedItem, config: Mock, filter_string: str) -> object:
    """The answer of ``filter_single_need``, or the message of the error it reports."""
    try:
        return filter_single_need(need, config, filter_string)
    except NeedsInvalidFilter as error:
        return str(error)


@pytest.mark.parametrize(
    "name",
    [
        # eval binds `search` to the regex function, whatever the need holds
        pytest.param("search", id="search"),
        # eval's globals hold the builtins under this name
        pytest.param("__builtins__", id="builtins-module"),
        # a module attribute, which eval does not find among its builtins
        pytest.param("__class__", id="dunder"),
    ],
)
def test_a_name_eval_binds_otherwise_stays_with_eval(name: str) -> None:
    """A name eval binds to something no field holds is no operand of the parsed tier:
    the string falls to eval, and answers what eval answers."""
    filter_string = f"owner != {name}"
    compiled = compile_portable(filter_string)
    assert compiled.predicate is None
    assert compiled.rejection == f"name:{name}"
    config = Mock()
    config.filter_data = {}
    need = _make_need(extras={"owner": "alice"})
    answer = _outcome(need, config, filter_string)
    refused = CompiledFilter(None, "refused", False)
    with patch.object(filter_common, "compile_portable", lambda _: refused):
        assert _outcome(need, config, filter_string) == answer


@pytest.mark.parametrize(
    "filter_string",
    [
        pytest.param('__class__ != "x"', id="module-attribute"),
        pytest.param('__name__ == "builtins"', id="module-dunder"),
    ],
)
def test_a_builtins_module_attribute_is_no_builtin(filter_string: str) -> None:
    """The builtins a name reads are the builtins module's own names, never the
    attributes every module object has nor its dunders: compared with a literal, such a
    name stays undefined, as it was before the grammar was the reference."""
    config = Mock()
    config.filter_data = {}
    need = _make_need()
    assert compile_portable(filter_string).predicate is not None
    with pytest.raises(NeedsInvalidFilter, match="is not defined"):
        filter_single_need(need, config, filter_string)


def test_the_origin_key_is_no_name_a_filter_can_hold() -> None:
    """The document reaches a predicate under a key no field or filter-data key can be,
    so a field named like it is never read as the document."""
    assert not ORIGIN_KEY.isidentifier()
