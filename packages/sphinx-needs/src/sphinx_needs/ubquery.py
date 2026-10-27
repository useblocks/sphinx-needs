"""The portable filter language: the tier of filter evaluation that needs no ``eval``.

A filter string is answered by the first of three tiers that takes it: the index path
(``filter_common._analyze_and_apply_expr``, a few shapes answered from the indexes of a
:class:`.NeedsView`), the predicates compiled here, and Python's ``eval`` of the string
against each need. This module compiles exactly the portable filter grammar, the subset
of Python expressions the portable filter language admits:
``tests/fixtures/filter_conformance.toml`` defines it and holds the three tiers to each
other's answers. The grammar is shared with ubCode's filter (``py_expr.pest`` there), so
a string inside it is read alike by both tools; each arm below names the rule it mirrors.

What a compiled predicate saves is cost, not semantics. ``eval`` resolves names lazily
too, and short-circuits ``and``/``or`` as a predicate does, so
``type == "spec" and spec_field == "x"`` reads ``spec_field`` of no need of another type
in either tier, and neither reports it undefined there (#2255). The cost of ``eval`` is
its context: every field of a need is copied into a fresh dict before the expression
runs, and that is nearly all of what it spends. A predicate reads only the fields the
expression reaches.

Its answers are ``eval``'s: for every string it compiles, a predicate gives the answer
``eval`` gives on the same need, errors included -- a name that is no field, no
``needs_filter_data`` key and no Python builtin raises :class:`NameError`, a method of a
value of the wrong type raises what Python raises, and ``c.this_doc()`` with no document
to compare raises the error the ``eval`` tier's context raises. Both read a filter's
value for its truth, by Python's rules, whatever its type (#1773); a filter that is a
constant alone is refused before either runs (``filter_common._is_constant_filter``).

A string outside the grammar is not an error here. :func:`try_build_simple_predicate`
returns ``None`` for it, the caller falls back to ``eval``, and :func:`compile_portable`
names the construct that kept it out, for the ``needs_debug_filters`` report.

A few forms this module took before the grammar was its reference are kept, although
the grammar lacks them: an ordering comparison of a name with a literal that is no
number, a tuple or a set of literals after ``in``, and a constant the grammar has no
literal for (``b"x"``) beside a name. It reads the string's syntax tree, not its text,
and puts no limit on its size, so it also compiles what the grammar leaves out for
spelling or size alone, each of which answers as eval answers it: ``not not x`` beside
``not (not x)``, a parenthesised operand, a trailing comma, a comment, triple quotes,
``.5``, ``1e+5``, ``-(1)``, a name that is not ASCII; an integer outside the signed 64-bit range, more
than 10 000 alternatives of conjunctions once expanded, nesting deeper than 64, a
string longer than 16 KiB.

The public entry point is :func:`try_build_simple_predicate`.
"""

from __future__ import annotations

import ast
import builtins
import operator
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache, partial
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

#: The ordering comparisons, which the grammar allows against a number literal only.
_ORDERING_OPS: tuple[type, ...] = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def _is_dunder(name: str) -> bool:
    """Whether *name* is a ``__dunder__`` name."""
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


#: Names injected into the eval context by the slow path that are *not* need fields.
#: If a filter references these, the fast path must bail out (return None).
_CONTEXT_ONLY_NAMES: frozenset[str] = frozenset({"needs", "current_need", "c", "var"})

#: The builtins a name that no key defines reads, as eval finds them: the builtins
#: module's own names (not the attributes every module object has, such as
#: ``__class__``), and no ``__dunder__`` name, which no operand takes (:func:`_field`).
_BUILTINS: Mapping[str, Any] = {
    name: value for name, value in vars(builtins).items() if not _is_dunder(name)
}

#: Names eval binds to something no field holds, so that no operand of this module
#: takes them (beside every ``__dunder__`` name, ``__builtins__`` among them): ``search``
#: is eval's regex function whatever the need holds. The comparisons this module took
#: before the grammar was its reference keep reading a plain name as they did.
_EVAL_BOUND: frozenset[str] = frozenset({"search"})

#: Root names that live in the fallback context (not on the need itself).
#: Attribute chains starting with these are resolved via the fallback mapping.
_FALLBACK_ROOTS: frozenset[str] = frozenset({"var"})

#: The key, in the per-call context mapping, of the document the filter is written in:
#: what ``c.this_doc()`` compares a need's document with. No name in a filter can be it,
#: so it never shadows a field. ``filter_common`` sets it, for a filter that reads it.
ORIGIN_KEY = "\x00origin"

#: What the literal readers return for a node that is no literal of theirs
#: (``None`` is a literal of the grammar, so it cannot be the marker).
_NOT_LITERAL: Any = object()


def _unpack_attribute_chain(node: ast.expr) -> tuple[str, ...] | None:
    """Unpack an AST attribute chain into a tuple of names.

    E.g. ``var.build.debug`` → ``("var", "build", "debug")``.
    Returns None if the node is not a simple attribute chain of Names.
    """
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        parts.reverse()
        return tuple(parts)
    return None


def _resolve_chain(ctx: Mapping[str, Any] | None, chain: tuple[str, ...]) -> Any:
    """Resolve an attribute chain against the fallback context.

    E.g. chain=("var", "cpu") looks up ctx["var"].cpu
    """
    if ctx is None or chain[0] not in ctx:
        raise NameError(f"name {chain[0]!r} is not defined")
    obj: Any = ctx[chain[0]]
    for segment in chain[1:]:
        obj = getattr(obj, segment)
    return obj


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


def _read_name(
    name: str,
    need: NeedItem | NeedPartItem,
    fallback: Mapping[str, Any] | None = None,
) -> Any:
    """The value of a name used as an operand: :func:`_get_field`, then Python's
    builtins, where eval finds a name that no key of its context defines -- so that
    ``owner != filter`` answers what eval answers rather than ``filter`` being undefined.

    The name comes first, for :func:`functools.partial` to bind it: an operand's reader
    is then called with no Python frame of its own between the predicate and this.
    """
    if fallback is not None and name in fallback:
        return fallback[name]
    if name in need:
        return need[name]
    if name in _BUILTINS:
        return _BUILTINS[name]
    raise NameError(f"name {name!r} is not defined")


def _read_chain(
    chain: tuple[str, ...],
    need: NeedItem | NeedPartItem,
    fallback: Mapping[str, Any] | None = None,
) -> Any:
    """:func:`_resolve_chain`, as a reader for :func:`functools.partial` to bind."""
    return _resolve_chain(fallback, chain)


#: Type alias for predicates returned by the fast-path builder.
#: The second argument is an optional fallback mapping (e.g. ``config.filter_data``).
SimplePredicate = Callable[[NeedItem | NeedPartItem, Mapping[str, Any] | None], bool]

#: What an operand compiles to: a reader of its value, from a need and the mapping.
_Getter = Callable[[NeedItem | NeedPartItem, Mapping[str, Any] | None], Any]


class _NotPortable(Exception):
    """Raised while compiling: the string holds a construct the grammar has no rule for.

    :param reason: a short stable name of the construct, for the debug report.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class CompiledFilter:
    """A filter string, compiled to a predicate or refused with the reason why."""

    predicate: SimplePredicate | None
    """The predicate, or None when the string is outside the portable grammar."""
    rejection: str | None
    """For a refused string, the construct that kept it out (``subscript``,
    ``call:any``, ``name:needs``, ...); None when it compiled."""
    reads_origin: bool
    """Whether the predicate reads the document the filter is written in
    (``c.this_doc()``): the caller then passes it under :data:`ORIGIN_KEY`."""


@lru_cache(maxsize=256)
def compile_portable(filter_string: str) -> CompiledFilter:
    """Compile a filter string of the portable grammar, once per string.

    The document a filter is written in is NOT part of the result, which every call
    with the same string shares: a predicate that reads it finds it in the mapping it
    is called with.
    """
    try:
        tree = ast.parse(filter_string, mode="eval")
    except (SyntaxError, ValueError):
        return CompiledFilter(None, "syntax", False)
    try:
        predicate = _expr(tree.body)
    except _NotPortable as refused:
        return CompiledFilter(None, refused.reason, False)
    return CompiledFilter(predicate, None, any(map(_is_this_doc, ast.walk(tree))))


def try_build_simple_predicate(
    filter_string: str,
) -> SimplePredicate | None:
    """Try to compile a filter string into a native Python predicate.

    Returns None if the string is outside the portable grammar, for the caller to
    fall back to ``eval``; :func:`compile_portable` says why.
    """
    return compile_portable(filter_string).predicate


def _expr_to_predicate(expr: ast.expr) -> SimplePredicate | None:
    """Compile an expression node to a predicate, or return None outside the grammar."""
    try:
        return _expr(expr)
    except _NotPortable:
        return None


def _is_c_check(node: ast.AST, check: str) -> bool:
    """Whether *node* is a call of ``c.<check>``, whatever its arguments."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == check
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "c"
    )


def _is_this_doc(node: ast.AST) -> bool:
    """Whether *node* is a call of ``c.this_doc``, whatever its arguments."""
    return _is_c_check(node, "this_doc")


# --- expressions: `or_expr`, `and_expr`, `not_expr`, `expr` ---


def _expr(node: ast.expr) -> SimplePredicate:
    """Compile an expression of the grammar to a predicate.

    :raises _NotPortable: For a construct outside the grammar.
    """
    # `or_expr` / `and_expr`: the operands are called left to right, and stop where
    # Python's `and` / `or` stop
    if isinstance(node, ast.BoolOp):
        preds = tuple(_expr(value) for value in node.values)
        if isinstance(node.op, ast.And):
            return lambda need, ctx=None, _fns=preds: all(fn(need, ctx) for fn in _fns)
        return lambda need, ctx=None, _fns=preds: any(fn(need, ctx) for fn in _fns)

    # `not_expr`
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _expr(node.operand)
        return lambda need, ctx=None, _fn=inner: not _fn(need, ctx)

    if isinstance(node, ast.Compare):
        return _compare(node)

    if isinstance(node, ast.Call):
        call = _call(node)
        if call is not None:
            return call

    # `bool_literal_expr`: `True` / `False`
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return lambda need, ctx=None, _v=node.value: _v

    # `var_field_op_expr` with no operator: the operand, read by its truthiness. A bare
    # name that is no field stays undefined rather than reading a Python builtin, which
    # eval would read as true: the language has no builtins, so the need is excluded
    # and the filter reported
    if (name := _plain_name(node)) is not None:
        return lambda need, ctx=None, _f=name, _r=_get_field: bool(_r(need, _f, ctx))
    get = _operand(node)
    return lambda need, ctx=None, _g=get: bool(_g(need, ctx))


def _call(node: ast.Call) -> SimplePredicate | None:
    """Compile a call that is an expression of its own, or return None for another.

    The grammar has four: ``c.this_doc()``, ``c.is_a("...")``, ``search(...)``, and a
    string predicate method (``x.startswith("...")``). ``len(x)``, ``x.lower()`` and
    ``x.upper()`` are operands, which :func:`_operand` compiles.

    :raises _NotPortable: For one of the four in a shape the grammar has no rule for.
    """
    func = node.func

    # `this_doc_check`: c.this_doc()
    if _is_this_doc(node):
        if node.args or node.keywords:
            raise _NotPortable("call:c.this_doc")
        return _this_doc

    # `is_a_check`: c.is_a("<type>"), which is "<type>" in type_ancestors
    if _is_c_check(node, "is_a"):
        name = _string(node.args[0]) if len(node.args) == 1 else None
        if name is None or node.keywords:
            raise _NotPortable("call:c.is_a")
        return partial(_is_a, name)

    # `search_check`: search("<pattern>", <operand>)
    if isinstance(func, ast.Name) and func.id == "search":
        if len(node.args) != 2 or node.keywords:
            raise _NotPortable("call:search")
        pattern = _string(node.args[0])
        if pattern is None or not _is_operand_shape(node.args[1]):
            raise _NotPortable("call:search")
        get = _operand(node.args[1])
        try:
            compiled = re.compile(pattern)
        except re.error:
            # the eval tier reports the pattern, need by need, as it always has
            raise _NotPortable("call:search") from None
        return lambda need, ctx=None, _rx=compiled, _g=get: (
            _rx.search(_g(need, ctx)) is not None
        )

    # `var_field_op_expr` with a `str_predicate_method`:
    # <operand>.startswith("<string>"), <operand>.endswith("<string>")
    if isinstance(func, ast.Attribute) and func.attr in ("startswith", "endswith"):
        argument = _string(node.args[0]) if len(node.args) == 1 else None
        if argument is None or node.keywords or not _is_operand_shape(func.value):
            raise _NotPortable(f"method:{func.attr}")
        get = _operand(func.value)
        method = operator.methodcaller(func.attr, argument)
        return lambda need, ctx=None, _g=get, _m=method: _m(_g(need, ctx))

    return None


def _this_doc(
    need: NeedItem | NeedPartItem, ctx: Mapping[str, Any] | None = None
) -> bool:
    """``c.this_doc()``: whether the need is in the document the filter is written in.

    As the ``eval`` tier's ``NeedCheckContext.this_doc``, which raises the same error
    where there is no such document (a filter configured in ``conf.py``).
    """
    origin = None if ctx is None else ctx.get(ORIGIN_KEY)
    if origin is None:
        raise ValueError("`this_doc` can not be used in this context")
    return need.is_in_document(origin)


def _is_a(
    name: str, need: NeedItem | NeedPartItem, ctx: Mapping[str, Any] | None = None
) -> bool:
    """``c.is_a("<name>")``: whether the need's type is *name* or inherits from it.

    As the ``eval`` tier's ``NeedCheckContext.is_a``, it reads the need's own
    ``type_ancestors``, never a ``needs_filter_data`` key of that name.
    """
    return name in need["type_ancestors"]


# --- comparisons: `comparison_expr`, `literal_cmp_var_field_expr`, `in`, `is None` ---


def _compare(node: ast.Compare) -> SimplePredicate:
    """Compile a comparison of the grammar to a predicate.

    :raises _NotPortable: For a comparison outside the grammar.
    """
    if len(node.ops) != 1:
        raise _NotPortable("compare:chained")
    op = node.ops[0]
    left, right = node.left, node.comparators[0]

    # `is_null_expr` / `is_not_null_expr`: <operand> is None, <operand> is not None
    if isinstance(op, ast.Is | ast.IsNot):
        if not (isinstance(right, ast.Constant) and right.value is None):
            raise _NotPortable("compare:is")
        get = _operand(left)
        if isinstance(op, ast.Is):
            return lambda need, ctx=None, _g=get: _g(need, ctx) is None
        return lambda need, ctx=None, _g=get: _g(need, ctx) is not None

    if isinstance(op, ast.In | ast.NotIn):
        return _membership(left, right, negate=isinstance(op, ast.NotIn))

    op_fn = _COMPARE_OPS[type(op)]
    ordering = isinstance(op, _ORDERING_OPS)

    # `comparison_expr` against a literal: <operand> == "x", <operand> > 5
    value = _comparison_literal(right, left, ordering=ordering)
    if value is not _NOT_LITERAL:
        if (name := _plain_name(left)) is not None:
            return lambda need, ctx=None, _f=name, _v=value, _op=op_fn, _r=_read_name: (
                _op(_r(_f, need, ctx), _v)
            )
        get = _operand(left)
        return lambda need, ctx=None, _g=get, _v=value, _op=op_fn: _op(
            _g(need, ctx), _v
        )

    # `literal_cmp_var_field_expr`: "x" == <operand>, 5 < <operand>
    value = _comparison_literal(left, right, ordering=ordering)
    if value is not _NOT_LITERAL:
        if (name := _plain_name(right)) is not None:
            return lambda need, ctx=None, _f=name, _v=value, _op=op_fn, _r=_read_name: (
                _op(_v, _r(_f, need, ctx))
            )
        get = _operand(right)
        return lambda need, ctx=None, _g=get, _v=value, _op=op_fn: _op(
            _v, _g(need, ctx)
        )

    # `comparison_expr` against an operand, in every comparison: <operand> == <operand>;
    # the left one is read first, as eval reads it
    for side in (left, right):
        if isinstance(side, ast.List):
            # a list beside a comparison is outside the grammar
            raise _NotPortable("compare:list")
        if ordering and _literal(side) is not _NOT_LITERAL:
            # an ordering comparison takes no literal but a number
            raise _NotPortable("compare:ordering")
    get_left, get_right = _operand(left), _operand(right)
    return lambda need, ctx=None, _l=get_left, _r=get_right, _op=op_fn: _op(
        _l(need, ctx), _r(need, ctx)
    )


def _membership(left: ast.expr, right: ast.expr, *, negate: bool) -> SimplePredicate:
    """Compile ``in`` / ``not in``.

    The grammar has two: an operand in a list of literals (`in_list_expr`,
    `not_in_list_expr`), and a literal in an operand (`literal_in_var_field_expr`,
    `literal_not_in_var_field_expr`). An operand in an operand is not one of them, so
    it stays with ``eval``.

    :raises _NotPortable: For any other membership test.
    """
    # <operand> in [<literal>, ...]
    if isinstance(right, ast.List | ast.Tuple | ast.Set):
        values = _members(right, legacy=isinstance(left, ast.Name))
        name = _plain_name(left)
        get = partial(_read_name, name) if name is not None else _operand(left)
        if isinstance(right, ast.Set):
            # eval builds a set, so a value that cannot be hashed fails there too
            hashed = frozenset(values)
            if negate:
                return lambda need, ctx=None, _g=get, _v=hashed: _g(need, ctx) not in _v
            return lambda need, ctx=None, _g=get, _v=hashed: _g(need, ctx) in _v
        return _sequence_member(name, get, tuple(values), negate=negate)

    # "<literal>" in <operand>
    value = _comparison_literal(left, right, ordering=False)
    if value is not _NOT_LITERAL:
        if (name := _plain_name(right)) is not None:
            if negate:
                return lambda need, ctx=None, _f=name, _v=value, _r=_read_name: (
                    _v not in _r(_f, need, ctx)
                )
            return lambda need, ctx=None, _f=name, _v=value, _r=_read_name: (
                _v in _r(_f, need, ctx)
            )
        get = _operand(right)
        if negate:
            return lambda need, ctx=None, _g=get, _v=value: _v not in _g(need, ctx)
        return lambda need, ctx=None, _g=get, _v=value: _v in _g(need, ctx)

    if _is_operand_shape(left) and _is_operand_shape(right):
        raise _NotPortable("compare:name-in-name")
    raise _NotPortable("compare:in")


def _sequence_member(
    name: str | None, get: _Getter, values: tuple[Any, ...], *, negate: bool
) -> SimplePredicate:
    """Membership of an operand in a list or a tuple of literals, as Python's ``in``
    reads it there.

    A hashed lookup gives the answer the sequence gives for every value that can be
    hashed; a value that cannot (a list, a dict) is compared item by item instead, as
    eval compares it, rather than raising where eval does not. A plain *name* is read
    directly, the other operands through *get*.
    """
    hashed = frozenset(values)

    def member(
        need: NeedItem | NeedPartItem, ctx: Mapping[str, Any] | None = None
    ) -> bool:
        value = _read_name(name, need, ctx) if name is not None else get(need, ctx)
        try:
            found = value in hashed
        except TypeError:
            found = value in values
        return not found if negate else found

    return member


def _members(node: ast.List | ast.Tuple | ast.Set, *, legacy: bool) -> list[Any]:
    """The literals of the container after ``in``.

    The grammar's `list_literal` is a list of literals (`literal_single`). *legacy* keeps
    what this module took before the grammar was its reference: after a plain name, a
    tuple or a set as well as a list, of any constants.

    :raises _NotPortable: For another container, or another member.
    """
    if isinstance(node, ast.List):
        values = [_literal(element) for element in node.elts]
        if all(value is not _NOT_LITERAL for value in values):
            return values
    if legacy and all(isinstance(element, ast.Constant) for element in node.elts):
        return [
            element.value for element in node.elts if isinstance(element, ast.Constant)
        ]
    if isinstance(node, ast.List):
        raise _NotPortable("compare:in")
    raise _NotPortable(type(node).__name__.lower())


def _comparison_literal(node: ast.expr, other: ast.expr, *, ordering: bool) -> Any:
    """The value of *node*, if it is the literal side of a comparison with *other*.

    The grammar's literal there is a `literal_single` (a string, a number, ``True``,
    ``False``, ``None``), and only a `number_literal` in an ordering comparison. Beside
    a plain name or an attribute chain any constant is kept, as this module took it
    before the grammar was its reference.

    :return: The value, or :data:`_NOT_LITERAL`.
    """
    if isinstance(node, ast.Constant) and isinstance(other, ast.Name | ast.Attribute):
        return node.value
    return _number(node) if ordering else _literal(node)


def _literal(node: ast.expr) -> Any:
    """The value of a `literal_single`: a string, a number, ``True``, ``False``, ``None``.

    :return: The value, or :data:`_NOT_LITERAL` for any other node.
    """
    if isinstance(node, ast.Constant):
        if node.value is None or isinstance(node.value, bool | int | float | str):
            return node.value
        return _NOT_LITERAL
    return _number(node)


def _number(node: ast.expr) -> Any:
    """The value of a `number_literal`: an integer or a float, a negative one included.

    ``True`` and ``False`` are no numbers of the grammar, although Python's are ints.

    :return: The value, or :data:`_NOT_LITERAL` for any other node.
    """
    negative = isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
    if isinstance(node, ast.UnaryOp) and negative:
        node = node.operand
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int | float)
        and not isinstance(node.value, bool)
    ):
        return -node.value if negative else node.value
    return _NOT_LITERAL


def _string(node: ast.expr) -> str | None:
    """The value of a `string_literal`, or None for any other node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


# --- operands: `var_field_with_func` and `var_field` ---


def _is_operand_shape(node: ast.expr) -> bool:
    """Whether *node* has the shape of an operand (a name, an attribute chain, a call)
    rather than of a literal or another expression; whether it compiles is for
    :func:`_operand` to say."""
    return isinstance(node, ast.Name | ast.Attribute | ast.Call)


def _plain_name(node: ast.expr) -> str | None:
    """The name, if *node* is a plain name a field can hold (not one eval binds to its
    own context), for the arms that read it with no reader in between: they then cost
    what they cost before the other operands existed."""
    if isinstance(node, ast.Name) and node.id not in _CONTEXT_ONLY_NAMES:
        return node.id
    return None


def _operand(node: ast.expr) -> _Getter:
    """Compile an operand (`var_field_with_func`): a field, ``len(<field>)``,
    ``<field>.lower()`` or ``<field>.upper()``.

    Each reads its field and calls on it what eval calls: the builtin ``len``, and the
    value's own ``lower`` or ``upper``, so that a value without one raises the
    :class:`AttributeError` eval raises.

    :raises _NotPortable: For anything else.
    """
    if isinstance(node, ast.Call):
        func = node.func
        # `var_field_with_len`: len(<field>)
        if isinstance(func, ast.Name) and func.id == "len":
            if len(node.args) != 1 or node.keywords:
                raise _NotPortable("call:len")
            get = _field(node.args[0], within="call:len")
            return lambda need, ctx=None, _g=get: len(_g(need, ctx))
        # `var_field_with_lower` / `var_field_with_upper`: <field>.lower(), .upper()
        if isinstance(func, ast.Attribute) and func.attr in ("lower", "upper"):
            if node.args or node.keywords:
                raise _NotPortable(f"method:{func.attr}")
            get = _field(func.value, within=f"method:{func.attr}")
            method = operator.methodcaller(func.attr)
            return lambda need, ctx=None, _g=get, _m=method: _m(_g(need, ctx))
        raise _NotPortable(_describe(node))
    return _field(node)


def _field(node: ast.expr, *, within: str | None = None) -> _Getter:
    """Compile a field (`var_field`): a name, or a ``var.`` chain.

    A name that no key defines reads a Python builtin, as eval reads it
    (:func:`_read_name`).

    :param within: the reason to give for a node that is no field and no other refused
        construct, when the field is the argument of an operand's call.
    :raises _NotPortable: For anything else.
    """
    # a name: a field of the need, or a `needs_filter_data` key
    if isinstance(node, ast.Name):
        if (
            node.id in _CONTEXT_ONLY_NAMES
            or node.id in _EVAL_BOUND
            or _is_dunder(node.id)
        ):
            raise _NotPortable(f"name:{node.id}")
        return partial(_read_name, node.id)
    # a dotted name: only the variant data's, var.<key>...
    if isinstance(node, ast.Attribute):
        chain = _unpack_attribute_chain(node)
        if chain is not None and chain[0] in _FALLBACK_ROOTS:
            return partial(_read_chain, chain)
        raise _NotPortable(_describe(node))
    if within is not None and not isinstance(node, ast.Subscript):
        raise _NotPortable(within)
    raise _NotPortable(_describe(node))


def _describe(node: ast.expr) -> str:
    """The reason to give for *node*, a construct the grammar has no rule for here."""
    if isinstance(node, ast.Name):
        return f"name:{node.id}"
    if isinstance(node, ast.Attribute):
        root: ast.expr = node
        while isinstance(root, ast.Attribute):
            root = root.value
        return f"attribute:{root.id}" if isinstance(root, ast.Name) else _describe(root)
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return f"call:{func.id}"
        if isinstance(func, ast.Attribute):
            chain = _unpack_attribute_chain(func)
            if chain is not None and chain[0] in _CONTEXT_ONLY_NAMES:
                return "call:" + ".".join(chain)
            return f"method:{func.attr}"
        return "call"
    if isinstance(node, ast.Subscript):
        return "subscript"
    if isinstance(node, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp):
        return "comprehension"
    if isinstance(node, ast.Constant) or _literal(node) is not _NOT_LITERAL:
        return "literal"
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return "not"
    if isinstance(node, ast.BinOp | ast.UnaryOp):
        return "arithmetic"
    if isinstance(node, ast.JoinedStr):
        return "fstring"
    # any other expression, by its kind: ifexp, lambda, tuple, set, dict, namedexpr, ...
    return type(node).__name__.lower()
