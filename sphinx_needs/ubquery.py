"""AST-based fast-path filter compilation for simple need expressions.

This module short-circuits ``eval()`` overhead for common filter patterns
(comparisons, membership tests, boolean combinators) by compiling filter
strings to native Python callables via the :mod:`ast` module.

Because field names are resolved lazily (only when the predicate actually
reaches them at runtime), short-circuit evaluation in ``and``/``or``
expressions means a predicate like ``type == "spec" and spec_field == "x"``
will never access ``spec_field`` for needs whose ``type`` is not ``"spec"``.
This opens a pathway to per-type fields
(see `discussion #1646 <https://github.com/useblocks/sphinx-needs/discussions/1646>`_),
which is not possible with ``eval()`` since it eagerly evaluates all names
in the expression context upfront.

The public entry point is :func:`try_build_simple_predicate`.
"""

from __future__ import annotations

import ast
import operator
import re
from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import Any

from sphinx_needs.need_item import NeedItem, NeedPartItem

_COMPARE_OPS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

#: Names injected into the eval context by the slow path that are *not* need fields.
#: If a filter references these, the fast path must bail out (return None).
_CONTEXT_ONLY_NAMES: frozenset[str] = frozenset({"needs", "current_need", "c"})


def _get_field(
    need: NeedItem | NeedPartItem,
    name: str,
    fallback: Mapping[str, Any] | None = None,
) -> Any:
    """Retrieve a field from a need, raising NameError if missing (mirrors eval).

    :param fallback: Optional mapping (e.g. ``config.filter_data``) checked
        **before** the need dict, matching the slow-path shadowing semantics
        where ``filter_context.update(config.filter_data)`` overwrites need fields.
    """
    if fallback is not None and name in fallback:
        return fallback[name]
    if name in need:
        return need[name]
    raise NameError(f"name {name!r} is not defined")


#: Type alias for predicates returned by the fast-path builder.
#: The second argument is an optional fallback mapping (e.g. ``config.filter_data``).
SimplePredicate = Callable[[NeedItem | NeedPartItem, Mapping[str, Any] | None], bool]


@lru_cache(maxsize=256)
def try_build_simple_predicate(
    filter_string: str,
) -> SimplePredicate | None:
    """Try to compile a filter string into a native Python predicate.

    Returns None if the expression is too complex to short-circuit.
    """
    try:
        tree = ast.parse(filter_string, mode="eval")
    except SyntaxError:
        return None
    return _expr_to_predicate(tree.body)


def _expr_to_predicate(
    expr: ast.expr,
) -> SimplePredicate | None:
    """Convert an AST expression to a native callable, or None if too complex.

    Each returned callable has signature ``(need, ctx) -> bool`` where *ctx*
    is an optional fallback mapping (e.g. ``config.filter_data``).
    """

    # --- comparisons: ==, !=, <, <=, >, >= ---
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1:
        op_type = type(expr.ops[0])

        if op_type in _COMPARE_OPS:
            field: str | None = None
            value: Any = None
            swapped = False
            if (
                isinstance(expr.left, ast.Name)
                and len(expr.comparators) == 1
                and isinstance(expr.comparators[0], ast.Constant)
            ):
                field = expr.left.id
                value = expr.comparators[0].value
            elif (
                isinstance(expr.left, ast.Constant)
                and len(expr.comparators) == 1
                and isinstance(expr.comparators[0], ast.Name)
            ):
                field = expr.comparators[0].id
                value = expr.left.value
                swapped = True

            if field is not None:
                if field in _CONTEXT_ONLY_NAMES:
                    return None
                op_fn = _COMPARE_OPS[op_type]
                if swapped:
                    return lambda need, ctx=None, _f=field, _v=value, _op=op_fn: _op(  # type: ignore[misc]
                        _v, _get_field(need, _f, ctx)
                    )
                return lambda need, ctx=None, _f=field, _v=value, _op=op_fn: _op(  # type: ignore[misc]
                    _get_field(need, _f, ctx), _v
                )

        # field in [literal, ...]
        if isinstance(expr.ops[0], ast.In):
            if (
                isinstance(expr.left, ast.Name)
                and len(expr.comparators) == 1
                and isinstance(expr.comparators[0], ast.List | ast.Tuple | ast.Set)
                and all(isinstance(e, ast.Constant) for e in expr.comparators[0].elts)
            ):
                field_name = expr.left.id
                if field_name in _CONTEXT_ONLY_NAMES:
                    return None
                values = frozenset(
                    e.value
                    for e in expr.comparators[0].elts
                    if isinstance(e, ast.Constant)
                )
                return lambda need, ctx=None, _f=field_name, _v=values: (  # type: ignore[misc]
                    _get_field(need, _f, ctx) in _v
                )

            # "value" in field  (e.g. "tag" in tags)
            if (
                isinstance(expr.left, ast.Constant)
                and len(expr.comparators) == 1
                and isinstance(expr.comparators[0], ast.Name)
            ):
                in_value = expr.left.value
                in_field = expr.comparators[0].id
                if in_field in _CONTEXT_ONLY_NAMES:
                    return None
                return lambda need, ctx=None, _f=in_field, _v=in_value: (  # type: ignore[misc]
                    _v in _get_field(need, _f, ctx)
                )

    # --- search(pattern, field) function call ---
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "search"
        and len(expr.args) == 2
        and not expr.keywords
        and isinstance(expr.args[0], ast.Constant)
        and isinstance(expr.args[0].value, str)
        and isinstance(expr.args[1], ast.Name)
        and expr.args[1].id not in _CONTEXT_ONLY_NAMES
    ):
        pattern = expr.args[0].value
        search_field = expr.args[1].id
        try:
            compiled = re.compile(pattern)
        except re.error:
            return None
        return lambda need, ctx=None, _rx=compiled, _f=search_field: (  # type: ignore[misc]
            _rx.search(_get_field(need, _f, ctx)) is not None
        )

    # --- bare name (e.g. is_external) ---
    if isinstance(expr, ast.Name):
        if expr.id in _CONTEXT_ONLY_NAMES:
            return None
        return lambda need, ctx=None, _f=expr.id: bool(_get_field(need, _f, ctx))  # type: ignore[misc]

    # --- not <expr> ---
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        inner = _expr_to_predicate(expr.operand)
        if inner is not None:
            return lambda need, ctx=None, _fn=inner: not _fn(need, ctx)  # type: ignore[misc]

    # --- <expr> and <expr> and ... ---
    if isinstance(expr, ast.BoolOp) and isinstance(expr.op, ast.And):
        preds = [_expr_to_predicate(v) for v in expr.values]
        if all(p is not None for p in preds):
            return lambda need, ctx=None, _fns=preds: all(fn(need, ctx) for fn in _fns)  # type: ignore[misc]

    # --- <expr> or <expr> or ... ---
    if isinstance(expr, ast.BoolOp) and isinstance(expr.op, ast.Or):
        preds = [_expr_to_predicate(v) for v in expr.values]
        if all(p is not None for p in preds):
            return lambda need, ctx=None, _fns=preds: any(fn(need, ctx) for fn in _fns)  # type: ignore[misc]

    return None
