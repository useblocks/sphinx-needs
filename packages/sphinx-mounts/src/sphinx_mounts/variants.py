"""Variant conditions and variant data — the ``[[source.variant_sources]]`` engine.

**Import discipline: this module is deliberately dependency-free.** It imports
nothing from :mod:`sphinx_mounts`, nothing from Sphinx and nothing from
docutils — only the standard library. The same is true of
:mod:`sphinx_mounts.dialect`. Both are written that way so that extracting
them into a shared ``sphinx-variants`` package later is a ``git mv`` rather
than a rewrite: the condition grammar is a two-engine contract (see
``tests/fixtures/variant_condition_conformance.toml``), and a contract that
can only live inside a mounting extension is one a second Sphinx extension
cannot adopt without depending on this one.

Anything that needs a Sphinx type — the ``ExtensionError`` wrapping, the
typed ``mounts.*`` warnings, ``config.root_doc`` — belongs in
:mod:`sphinx_mounts.config` or :mod:`sphinx_mounts.extension`, which catch the
plain exceptions raised here and re-raise them in Sphinx's vocabulary.

Two halves:

**The condition engine** (:func:`validate`, :func:`interpret`) is an
*interpreter*, not an :func:`eval` with a small globals dict. ``ast.parse``
produces one tree; :func:`validate` walks it against a whitelist, and
:func:`interpret` walks the *same* tree over the plain merged mapping. There
is no namespace object, no ``var`` binding and no builtins to remove, because
nothing is ever executed. That turns the whitelist's completeness from a
*security* property into a *correctness* one: a node type the interpreter does
not handle raises :class:`VariantEvalError` instead of running.

**The variant-data reader** (:func:`resolve_variant_data`) is a private copy of
sphinx-needs' ``deep_merge`` / ``validate_variant_data`` /
``load_variant_data_file`` semantics. The copy exists so that sphinx-mounts
never imports, depends on, or version-gates against sphinx-needs, and it cannot
disagree with it: ``deep_merge(file, inline)`` is idempotent, so re-merging an
already-merged map is a proven no-op. See :func:`resolve_variant_data`.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

#: Leaf value types the variant data may hold.
_SCALAR_TYPES = (str, bool, int, float)


class VariantConditionError(Exception):
    """A rule condition is outside the grammar — a *configuration* error.

    Statically knowable, so it is refused rather than evaluated. The caller
    turns this into a hard, non-suppressible failure.
    """


class VariantEvalError(Exception):
    """A rule condition is inside the grammar but cannot be *evaluated*.

    An unknown ``var.*`` key or a type mismatch. Data-dependent rather than
    statically knowable, so it is reported and the rule is treated as FALSE —
    the warn-and-exclude contract the ``.. if::`` directive already has, and
    the safe direction for a key whose purpose is keeping content out.
    """


class VariantDataError(Exception):
    """The variant data itself is unreadable or malformed.

    Deliberately the same name sphinx-needs uses for the same condition, so a
    reader comparing the two implementations is not misled by a rename.
    """


# ---------------------------------------------------------------------------
# The two bound tables
# ---------------------------------------------------------------------------
#
# The accept-set AND the comparison semantics below are MIRRORED ON UBCODE'S
# SHIPPED ENGINE, derived from its primary sources and confirmed against a live
# probe of it (`rust/ubc_query/src/py_expr.pest`, `py_expr.rs`, `filter.rs`,
# `rust/ubc_config/src/needs/variant_data.rs`). Both tables are reproduced
# verbatim in `design/mapping-contract.md` §12.5, which is the contract a third
# reader implements against.
#
# They deliberately depart from Python in places. That is the point: the same
# `if` string is read by two engines, and "one rule string, one document set"
# is worth more than matching CPython. `var.debug == 0` is FALSE here because
# it is false there — Python's `False == 0` would have made it true and the two
# tools would have built different sites from one file, silently.
#
# ubCode's own `docs/source/usage/variants.rst` claims the semantics match
# Python's. Measured, they do not; that is a defect in ubCode's documentation,
# named here rather than adopted. If the two engines ever move to Python
# semantics they move together, and this module and that engine change in the
# same release.


def _is_var_rooted(node: ast.AST) -> bool:
    """Whether ``node`` is ``var`` or a chain of plain attributes rooted at it.

    A leading-underscore segment is refused outright. Nothing can reach
    ``__class__`` through the interpreter anyway — it holds no objects, only
    the plain mapping — but refusing the spelling keeps the *grammar* the same
    shape as the one a future ``eval``-based reader would need.
    """
    while isinstance(node, ast.Attribute):
        if node.attr.startswith("_"):
            return False
        node = node.value
    return isinstance(node, ast.Name) and node.id == "var"


def _dotted(node: ast.AST) -> str:
    """Render an attribute chain / name as the author wrote it."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    parts.reverse()
    return ".".join(parts)


def _refuse_bare_name(name: str) -> None:
    """Raise the right message for a field reference not rooted at ``var``.

    ``true`` / ``false`` get their own sentence because they are by far the
    likeliest way a bare name appears: a TOML author writes the spelling TOML
    uses, and the parser reads it as a *field name*. Saying "write ``var.false``"
    would be accurate and useless.
    """
    if name.startswith("var."):
        # Rooted at `var`, but some segment starts with an underscore.
        msg = (
            f"`{name}` accesses a leading-underscore field, which a rule "
            f"condition may not name; variant data keys are ordinary names"
        )
        raise VariantConditionError(msg)
    if name in {"true", "false"}:
        python = "True" if name == "true" else "False"
        msg = (
            f"`{name}` is read as a field name, not as a boolean: a condition "
            f"is an expression rather than a TOML value, so the literals are "
            f"Python-spelled — write `{python}`"
        )
        raise VariantConditionError(msg)
    msg = (
        f"`{name}` is not rooted at `var`; a rule condition may only reference "
        f"the variant data, so write `var.{name}`. Unlike the `if` directive, "
        f"the leading `var` is required here: a bare name is not expected to be "
        f"defined for every tool that reads this file, and would then select a "
        f"different set of documents"
    )
    raise VariantConditionError(msg)


# ---------------------------------------------------------------------------
# TABLE 1 — the accept-set
# ---------------------------------------------------------------------------
#
# Every shape the grammar admits, and nothing else. Established from ubCode's
# pest grammar plus its AST conversion, and confirmed by probing the shipped
# engine; the probe transcript is quoted in the build report.
#
# An expression is a boolean form:
#
#   boolean := boolean ('and'|'or') boolean
#            | 'not' boolean
#            | '(' boolean ')'
#            | comparison
#            | 'True' | 'False'
#            | receiver '.' ('startswith'|'endswith') '(' string ')'
#
# A comparison is exactly one of these seven rows — note that EVERY row carries
# at least one receiver, because ubCode has no DNF arm holding two literals
# (`True == True` and `'a' == 'b'` are parse errors there, not choices):
#
#   receiver ('=='|'!=') receiver | scalar-literal
#   scalar-literal ('=='|'!=') receiver
#   receiver ('<'|'>'|'<='|'>=') receiver | number-literal
#   number-literal ('<'|'>'|'<='|'>=') receiver
#   receiver ('in'|'not in') '[' scalar-literal, … ']'
#   scalar-literal ('in'|'not in') receiver
#   receiver ('is'|'is not') 'None'
#
#   receiver       := 'var' ('.' name)+ ('.upper()' | '.lower()')?
#   scalar-literal := string | integer | float | 'True' | 'False' | 'None'
#                     (integers and floats may carry a leading '-')
#   number-literal := integer | float, negatives included; NOT bool, None or
#                     string
#
# The consequences that today's Python-shaped whitelist got wrong, each a
# measured divergence rather than a tightening for its own sake:
#
#   * a list literal is legal ONLY as the right-hand side of `in`/`not in`
#     (`var.tags == ['alpha','beta']` → ubCode refuses, Python evaluates TRUE);
#   * `in`/`not in` never take a string or a field on the right
#     (`var.edition in 'professional'`, `var.edition not in var.name` → ubCode
#     refuses, Python evaluates TRUE);
#   * a predicate call cannot appear inside a comparison
#     (`var.name.startswith('W') == True` → refused; `.upper()` inside one is
#     fine, which is the asymmetry an author will not guess);
#   * an ordering operator takes only a number on the literal side
#     (`var.edition < 'x'`, `var.count < True` → refused);
#   * a comparison with no receiver at all is refused;
#   * a NEGATIVE numeric literal is ACCEPTED (`var.count == -2`) — ubCode's
#     `integer_literal` carries `"-"?` — while a unary `+` is refused;
#   * implicit string concatenation (`'Wid' 'get'`) is refused: Python folds it
#     at parse time and ubCode's grammar has no such rule.

#: Methods usable on a ``var.*`` chain, split by RETURN TYPE.
#:
#: The boolean-top-level rule is type-aware and the conformance corpus is what
#: says so: rows 16/17 ACCEPT a bare ``var.name.startswith('Wid')`` /
#: ``.endswith('get')`` (they return ``bool``), while rows 34/35 REJECT a bare
#: ``var.name.upper()`` / ``.lower()`` (they return ``str``). Prose summaries of
#: the grammar — ubCode's own schema doc comment and its ``usage/variants.rst``
#: — say "bare string-method calls" are refused, which is imprecise.
_PREDICATE_METHODS = frozenset({"startswith", "endswith"})
_TRANSFORM_METHODS = frozenset({"upper", "lower"})

_ORDER_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_EQ_OPS = (ast.Eq, ast.NotEq)
_IN_OPS = (ast.In, ast.NotIn)
_IS_OPS = (ast.Is, ast.IsNot)


def _receiver(node: ast.AST) -> ast.AST | None:
    """Return the ``var.*`` chain ``node`` reads, or ``None``.

    A receiver is a ``var``-rooted attribute chain, optionally carrying ONE
    transformer suffix (``.upper()`` / ``.lower()``). ubCode's
    ``var_field_with_func`` is exactly this, and it admits only one function —
    ``var.name.upper().upper()`` is a parse error there, so it is refused here.
    """
    if isinstance(node, ast.Call):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in _TRANSFORM_METHODS
            and not node.args
            and not node.keywords
            and _is_var_rooted(func.value)
            and isinstance(func.value, ast.Attribute)
        ):
            return func.value
        return None
    if isinstance(node, ast.Attribute) and _is_var_rooted(node):
        return node
    return None


def _negative_literal_kind(node: ast.UnaryOp) -> str | None:
    """Classify a ``-2`` / ``-1.5`` literal, or return ``None``.

    ubCode's ``integer_literal = @{ "-"? ~ … }`` makes the sign part of the
    literal. The spellings that separate ``-2`` from ``- 2`` and from ``+2``
    are the recogniser's business — it works on the raw text, where the
    difference survives — so this only has to say what KIND the literal is.
    """
    if not isinstance(node.op, ast.USub):
        return None
    operand = node.operand
    if not isinstance(operand, ast.Constant) or isinstance(operand.value, bool):
        return None
    if not isinstance(operand.value, int | float):
        return None
    return "int" if isinstance(operand.value, int) else "float"


def _literal_kind(node: ast.AST) -> str | None:
    """Classify ``node`` as a scalar literal, or return ``None``.

    Returns one of ``"str"``, ``"bool"``, ``"int"``, ``"float"``, ``"null"``.
    """
    if isinstance(node, ast.UnaryOp):
        return _negative_literal_kind(node)
    if not isinstance(node, ast.Constant):
        return None
    value = node.value
    if isinstance(value, str):
        return "str"
    for kind, python_type in _CONSTANT_KINDS:
        if isinstance(value, python_type):
            return kind
    return "null" if value is None else None


def _value_kind(node: ast.AST) -> str:
    """The kind of an ALREADY-VALIDATED literal, without consulting the source.

    :func:`_literal_kind` needs the source text to tell ``-2`` from ``- 2`` and
    one string literal from an implicitly concatenated pair. Both are
    validation-only questions — by evaluation time the condition has already
    been accepted — so the interpreter uses this instead and stays a pure
    function of the tree.
    """
    if isinstance(node, ast.UnaryOp):
        operand = node.operand
        if isinstance(operand, ast.Constant) and isinstance(operand.value, int):
            return "int"
        return "float"
    if not isinstance(node, ast.Constant):  # pragma: no cover - validated
        msg = f"cannot evaluate `{type(node).__name__}` as a literal"
        raise VariantEvalError(msg)
    value = node.value
    if isinstance(value, str):
        return "str"
    if value is None:
        return "null"
    for kind, python_type in _CONSTANT_KINDS:
        if isinstance(value, python_type):
            return kind
    msg = f"cannot evaluate the literal {value!r}"  # pragma: no cover
    raise VariantEvalError(msg)  # pragma: no cover


def _literal_value(node: ast.AST) -> Any:
    """The value of a node :func:`_literal_kind` accepted."""
    if isinstance(node, ast.UnaryOp):
        operand = node.operand
        if isinstance(operand, ast.Constant) and isinstance(operand.value, int | float):
            # `validate` only admits a negated NUMBER, so this is the only
            # shape that reaches here.
            return -operand.value
    if isinstance(node, ast.Constant):
        return node.value
    msg = f"cannot read a literal from `{type(node).__name__}`"  # pragma: no cover
    raise VariantEvalError(msg)  # pragma: no cover


def _scalar_list(node: ast.AST) -> list[ast.AST] | None:
    """Return the elements of a list literal of scalars, or ``None``.

    A ``(…)`` tuple is deliberately not one: ubCode's grammar has a
    ``list_literal`` rule and no tuple rule at all.
    """
    if not isinstance(node, ast.List):
        return None
    for element in node.elts:
        if _literal_kind(element) is None:
            return None
    return list(node.elts)


def _refuse_operand(node: ast.AST, *, what: str) -> None:
    """Raise the most specific message available for a rejected operand."""
    if isinstance(node, ast.Name | ast.Attribute):
        _refuse_bare_name(_dotted(node))
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _PREDICATE_METHODS:
            msg = (
                f"`.{func.attr}()` may not appear inside a comparison; it is a "
                f"complete condition on its own. Write "
                f"`var.field.{func.attr}('…')`, optionally negated with `not`"
            )
            raise VariantConditionError(msg)
        name = _dotted(func) if isinstance(func, ast.Name | ast.Attribute) else "?"
        msg = (
            f"unsupported call `{name}`: only `.startswith()`, `.endswith()`, "
            f"`.upper()` and `.lower()` on a `var.*` field are available — there "
            f"are no builtins and no filter functions in a rule condition"
        )
        raise VariantConditionError(msg)
    if isinstance(node, ast.List | ast.Tuple):
        msg = (
            "a list literal is only allowed on the right of `in` / `not in`; "
            "compare against one value at a time, or write "
            "`var.field in ['a', 'b']`"
        )
        raise VariantConditionError(msg)
    if isinstance(node, ast.UnaryOp):
        msg = (
            "a sign is part of a numeric literal, so it must be written "
            "against the digits (`-2`, not `- 2`), and `+` is not accepted"
        )
        raise VariantConditionError(msg)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        msg = (
            "implicit string concatenation is not part of a rule condition; "
            "write the string as one literal"
        )
        raise VariantConditionError(msg)
    msg = (
        f"unsupported {what} `{type(node).__name__}`; a rule condition is "
        f"comparisons, `in` / `not in`, `is None` / `is not None`, "
        f"`.startswith(…)` / `.endswith(…)`, `and` / `or` / `not`, parentheses, "
        f"nested `var.*` access and the literals `True` / `False`"
    )
    raise VariantConditionError(msg)


def _validate_predicate_call(node: ast.Call) -> None:
    """Validate a terminal ``.startswith(…)`` / ``.endswith(…)`` call."""
    func = node.func
    if not isinstance(func, ast.Attribute):  # pragma: no cover - caller checks
        _refuse_operand(node, what="expression")
        return
    if _receiver(func.value) is None:
        msg = "a string predicate may only be called on a `var.*` field"
        raise VariantConditionError(msg)
    if node.keywords:
        msg = "keyword arguments are not supported"
        raise VariantConditionError(msg)
    if len(node.args) != 1 or _literal_kind(node.args[0]) != "str":
        msg = f"`.{func.attr}()` takes exactly one string literal"
        raise VariantConditionError(msg)


def _validate_compare(node: ast.Compare) -> None:
    """Validate one comparison against TABLE 1's seven rows."""
    if len(node.ops) != 1:
        msg = "chained comparisons are not supported; write them with `and`"
        raise VariantConditionError(msg)
    op = node.ops[0]
    left, right = node.left, node.comparators[0]

    if isinstance(op, _IS_OPS):
        if _receiver(left) is None:
            _refuse_operand(left, what="operand")
        if _literal_kind(right) != "null":
            msg = "`is` / `is not` may only be used with `None`"
            raise VariantConditionError(msg)
        return

    if isinstance(op, _IN_OPS):
        if _receiver(right) is not None:
            # `literal in var.field` — the container is the field.
            if _literal_kind(left) is None:
                _refuse_operand(left, what="left operand")
            return
        elements = _scalar_list(right)
        if elements is None:
            if isinstance(right, ast.Name | ast.Attribute):
                _refuse_bare_name(_dotted(right))
            msg = (
                "the right of `in` / `not in` must be a list literal of scalars "
                "(`var.field in ['a', 'b']`) or a `var.*` field with a literal "
                "on the left (`'a' in var.field`). A string or a field on the "
                "right is refused, because it is not part of the shared grammar"
            )
            raise VariantConditionError(msg)
        if _receiver(left) is None:
            _refuse_operand(left, what="left operand")
        return

    if isinstance(op, _EQ_OPS):
        _validate_symmetric(left, right, literal_kinds=None)
        return

    if isinstance(op, _ORDER_OPS):
        _validate_symmetric(left, right, literal_kinds=("int", "float"))
        return

    msg = f"unsupported comparison operator `{type(op).__name__}`"
    raise VariantConditionError(msg)


def _validate_symmetric(
    left: ast.AST,
    right: ast.AST,
    *,
    literal_kinds: tuple[str, ...] | None,
) -> None:
    """Validate an equality or ordering comparison.

    At least one side must be a receiver; the other may be a receiver or a
    literal of ``literal_kinds`` (``None`` meaning any scalar literal). Both
    sides being literals is refused — ubCode has no DNF arm for it.
    """
    left_receiver = _receiver(left) is not None
    right_receiver = _receiver(right) is not None
    if left_receiver and right_receiver:
        return
    if not left_receiver and not right_receiver:
        if _literal_kind(left) is not None and _literal_kind(right) is not None:
            msg = (
                "a comparison must reference the variant data; a comparison "
                "between two literals is always the same answer and is not part "
                "of the shared grammar"
            )
            raise VariantConditionError(msg)
        _refuse_operand(left if _receiver(left) is None else right, what="operand")
    literal_side = right if left_receiver else left
    kind = _literal_kind(literal_side)
    if kind is None:
        _refuse_operand(literal_side, what="operand")
    if literal_kinds is not None and kind not in literal_kinds:
        msg = (
            f"`<`, `>`, `<=` and `>=` compare numbers, so the other side must "
            f"be a number literal or another `var.*` field; got a {kind} literal"
        )
        raise VariantConditionError(msg)


def _refuse_non_boolean(node: ast.AST) -> None:
    """Raise for a sub-expression whose value is not a boolean."""
    if isinstance(node, ast.Name | ast.Attribute):
        name = _dotted(node)
        if not _is_var_rooted(node):
            _refuse_bare_name(name)
        msg = (
            f"`{name}` is used as a condition on its own, which is not a "
            f"boolean; compare it instead (for example `{name} == True`)"
        )
        raise VariantConditionError(msg)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        name = f"{_dotted(node.func.value)}.{node.func.attr}()"
        msg = (
            f"`{name}` returns a string, not a boolean, so it cannot be a "
            f"condition on its own; compare it instead (for example "
            f"`{name} == 'VALUE'`)"
        )
        raise VariantConditionError(msg)
    msg = (
        f"a rule condition must be boolean-valued; got "
        f"`{type(node).__name__}`. Write an explicit comparison"
    )
    raise VariantConditionError(msg)


def _validate_boolean(text: str, node: ast.AST) -> None:
    """Validate a boolean-valued sub-expression.

    ``not var.debug`` is refused even though its *top level* is boolean. The
    reason is parity: ubCode enforces the same rule over a flattened DNF, where
    a negation arrives as a negated leaf with nothing left to say whether it was
    the top level, so it refuses both. Narrower is the safe direction for a
    grammar two engines must agree on — a refused form is a configuration error
    the author rewrites once, never a silent disagreement about which documents
    exist. Corpus row: ``not var.debug`` → reject.
    """
    if isinstance(node, ast.BoolOp):
        for value in node.values:
            _validate_boolean(text, value)
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ast.Not):
            _refuse_non_boolean(node)
        _validate_boolean(text, node.operand)
        return
    if isinstance(node, ast.Compare):
        _validate_compare(node)
        return
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _PREDICATE_METHODS:
            # Type-aware: `.startswith()` / `.endswith()` return `bool`, so a
            # bare call IS a valid boolean top level (corpus rows 16, 17);
            # `.upper()` / `.lower()` return `str` and are not (rows 34, 35).
            _validate_predicate_call(node)
            return
        if isinstance(func, ast.Attribute) and func.attr in _TRANSFORM_METHODS:
            _refuse_non_boolean(node)
        _refuse_operand(node, what="expression")
    _refuse_non_boolean(node)


# ---------------------------------------------------------------------------
# TABLE 1b — the GRAMMAR RECOGNISER
# ---------------------------------------------------------------------------
#
# The kind-level table above works on Python's parsed tree. Python's tokenizer
# normalises away spellings ubCode's lexer refuses, so a validator working from
# the tree alone is not CLOSED: two rounds of review each produced a fresh
# class of leak (whitespace and numeral bases; then comments, `not not`,
# parenthesised operands, NFKC identifier folding), and every one of them let a
# rule ubCode drops be kept here — one string, two document sets.
#
# Enumerating refusals cannot converge on that, so this is not an enumeration.
# `_PestRecogniser` is a faithful port of ubCode's own grammar,
# `rust/ubc_query/src/py_expr.pest`, production by production, run over the RAW
# condition text BEFORE `ast.parse` sees it. It is closed by construction:
# anything the grammar does not derive is refused, whether or not anyone
# thought of it. Each method cites the pest line it ports.
#
# Two gates, deliberately: the recogniser owns SPELLING, and the AST pass above
# owns KINDS and SEMANTICS. Both must accept. The recogniser is therefore
# permissive about things ubCode's later passes refuse — a bare `var.debug`
# parses in pest and is refused by its DNF whitelist, exactly as it parses here
# and is refused by `_validate_boolean`.
#
# PEG semantics are reproduced, not approximated: an ordered choice commits to
# the first alternative that matches at a position, and a repetition stops at
# the first item that does not. Backtracking happens WITHIN a choice (each
# alternative restores the position on failure) and not across one that has
# already succeeded — which is what makes `var.count == 2 # c` fail at EOI
# rather than silently re-parsing.


class _PestRecogniser:
    """A recursive-descent recogniser for `py_expr.pest`.

    Recognises only — no tree is built, because the AST pass already has one.
    :meth:`accepts` answers the single question this class exists for: would
    ubCode's parser derive this text?
    """

    #: `reserved` (pest :74). A reserved word is a field name ONLY when it
    #: continues into a longer identifier (`Trueish`, `is_external`).
    _RESERVED = ("None", "True", "False", "and", "or", "not", "in", "is")

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    # -- primitives ---------------------------------------------------------

    def _at(self, literal: str) -> bool:
        """Consume ``literal`` if it is next."""
        if self.text.startswith(literal, self.pos):
            self.pos += len(literal)
            return True
        return False

    def _peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _ws(self) -> bool:
        """`ws` (pest :119) — space, tab, newline. Note: NOT carriage return."""
        if self._peek() in (" ", "\t", "\n"):
            self.pos += 1
            return True
        return False

    def _ws_star(self) -> None:
        while self._ws():
            pass

    def _ws_plus(self) -> bool:
        if not self._ws():
            return False
        self._ws_star()
        return True

    def _choice(self, *alternatives) -> bool:
        """PEG ordered choice: first alternative that matches wins."""
        for alternative in alternatives:
            save = self.pos
            if alternative():
                return True
            self.pos = save
        return False

    def _seq(self, *parts) -> bool:
        """PEG sequence: all or nothing, restoring the position on failure."""
        save = self.pos
        for part in parts:
            if not (part() if callable(part) else self._at(part)):
                self.pos = save
                return False
        return True

    # -- identifiers (pest :74-82) -----------------------------------------

    @staticmethod
    def _is_id_start(char: str) -> bool:
        """`id_start` (:81) — ASCII only, which is what refuses a folded
        fullwidth or modifier letter that Python's NFKC would accept."""
        return char == "_" or ("a" <= char <= "z") or ("A" <= char <= "Z")

    @classmethod
    def _is_id_part(cls, char: str) -> bool:
        """`id_part` (:82)."""
        return cls._is_id_start(char) or ("0" <= char <= "9")

    def _symbolic_name_simple(self) -> bool:
        """`symbolic_name_simple` (:80) — `!(reserved ~ !id_part) ~ id_start ~ id_part*`."""
        for word in self._RESERVED:
            if self.text.startswith(word, self.pos):
                after = self.pos + len(word)
                nxt = self.text[after] if after < len(self.text) else ""
                if not self._is_id_part(nxt):
                    return False  # it is the keyword, never a field
        if not self._is_id_start(self._peek()):
            return False
        self.pos += 1
        while self._is_id_part(self._peek()):
            self.pos += 1
        return True

    def _var_field(self) -> bool:
        """`var_field` (:67) — dotted segments, each with `!("(")` after it."""
        if not self._symbolic_name_simple():
            return False
        while True:
            save = self.pos
            if not self._at("."):
                return True
            if not self._symbolic_name_simple():
                self.pos = save
                return True
            if self._peek() == "(":
                # The negative lookahead: a segment followed by `(` belongs to
                # `.upper()` / `.startswith(…)`, not to the field.
                self.pos = save
                return True

    def _var_field_with_func(self) -> bool:
        """`var_field_with_func` (:69) — len / upper / lower / bare, in order."""
        return self._choice(
            lambda: self._seq("len(", self._var_field, ")"),
            lambda: self._seq(self._var_field, ".upper()"),
            lambda: self._seq(self._var_field, ".lower()"),
            self._var_field,
        )

    # -- literals (pest :84-106) -------------------------------------------

    def _integer_literal(self) -> bool:
        """`integer_literal` (:93) — `"-"? ~ ("0" | NONZERO ~ DIGIT*)`."""
        save = self.pos
        self._at("-")
        char = self._peek()
        if char == "0":
            self.pos += 1
            return True
        if "1" <= char <= "9":
            self.pos += 1
            while "0" <= self._peek() <= "9":
                self.pos += 1
            return True
        self.pos = save
        return False

    def _decimal_literal(self) -> bool:
        """`decimal_literal` (:94) — `integer ~ "." ~ DIGIT*`."""
        save = self.pos
        if not self._integer_literal() or not self._at("."):
            self.pos = save
            return False
        while "0" <= self._peek() <= "9":
            self.pos += 1
        return True

    def _exp(self) -> bool:
        """`exp` (:96) — case-insensitive `E` then an integer."""
        save = self.pos
        if self._peek() not in ("e", "E"):
            return False
        self.pos += 1
        if not self._integer_literal():
            self.pos = save
            return False
        return True

    def _float_literal(self) -> bool:
        """`float_literal` (:95) — `integer ~ exp | decimal ~ exp?`."""
        return self._choice(
            lambda: self._seq(self._integer_literal, self._exp),
            lambda: self._seq(self._decimal_literal, lambda: (self._exp(), True)[1]),
        )

    def _number_literal(self) -> bool:
        """`number_literal` (:92) — float, decimal, integer, in that order."""
        return self._choice(
            self._float_literal, self._decimal_literal, self._integer_literal
        )

    def _string_literal(self) -> bool:
        """`string_literal` (:98-102) — a backslash escapes the NEXT character
        for lexing only; nothing is decoded here."""
        quote = self._peek()
        if quote not in ("'", '"'):
            return False
        save = self.pos
        self.pos += 1
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\":
                self.pos += 2
                continue
            self.pos += 1
            if char == quote:
                return True
        self.pos = save
        return False

    def _boolean_literal(self) -> bool:
        """`boolean_literal` (:87)."""
        return self._at("True") or self._at("False")

    def _null_literal(self) -> bool:
        """`null_literal` (:88)."""
        return self._at("None")

    def _literal_single(self) -> bool:
        """`literal_single` (:84) — no list."""
        return self._choice(
            self._null_literal,
            self._boolean_literal,
            self._number_literal,
            self._string_literal,
        )

    def _list_literal(self) -> bool:
        """`list_literal` (:104-106) — no trailing comma, and no tuple form."""
        save = self.pos
        if not self._at("["):
            return False
        self._ws_star()
        if self._literal_single():
            self._ws_star()
            while True:
                item = self.pos
                if not (
                    self._at(",")
                    and (self._ws_star() or True)
                    and self._literal_single()
                ):
                    self.pos = item
                    break
                self._ws_star()
        if not self._at("]"):
            self.pos = save
            return False
        return True

    def _literal(self) -> bool:
        """`literal` (:85) — `literal_single` plus a list."""
        return self._choice(self._literal_single, self._list_literal)

    # -- operators and suffixes (pest :40-65, :108-113) --------------------

    def _str_predicate_method(self) -> bool:
        """`str_predicate_method` (:108) — no whitespace, no trailing comma."""
        return self._seq(
            ".",
            lambda: self._at("startswith") or self._at("endswith"),
            "(",
            self._string_literal,
            ")",
        )

    def _comparison_expr(self) -> bool:
        """`comparison_expr` (:45-52). `ws*`, so operators need no spacing.

        The operator order is pest's: `<` is tried before `<=`, and the `<=`
        input only reaches its own alternative because the `<` one fails on the
        `=` that follows.
        """

        def cmp(operator: str, right) -> bool:
            return self._seq(
                lambda: (self._ws_star(), True)[1],
                operator,
                lambda: (self._ws_star(), True)[1],
                right,
            )

        either = lambda: self._choice(self._literal, self._var_field_with_func)  # noqa: E731
        number = lambda: self._choice(self._number_literal, self._var_field_with_func)  # noqa: E731
        return self._choice(
            lambda: cmp("==", either),
            lambda: cmp("!=", either),
            lambda: cmp("<", number),
            lambda: cmp(">", number),
            lambda: cmp("<=", number),
            lambda: cmp(">=", number),
        )

    def _is_null_expr(self) -> bool:
        """`is_null_expr` (:61)."""
        return self._seq(self._ws_plus, "is", self._ws_plus, "None")

    def _is_not_null_expr(self) -> bool:
        """`is_not_null_expr` (:62)."""
        return self._seq(
            self._ws_plus, "is", self._ws_plus, "not", self._ws_plus, "None"
        )

    def _in_list_expr(self) -> bool:
        """`in_list_expr` (:64) — a list literal or a bare field on the right."""
        return self._seq(
            self._ws_plus,
            "in",
            self._ws_plus,
            lambda: self._choice(self._list_literal, self._var_field),
        )

    def _not_in_list_expr(self) -> bool:
        """`not_in_list_expr` (:65)."""
        return self._seq(
            self._ws_plus,
            "not",
            self._ws_plus,
            "in",
            self._ws_plus,
            lambda: self._choice(self._list_literal, self._var_field),
        )

    # -- expressions (pest :3-43) ------------------------------------------

    def _var_field_op_expr(self) -> bool:
        """`var_field_op_expr` (:40-43) — a field plus at most one suffix."""
        if not self._var_field_with_func():
            return False
        save = self.pos
        if not self._choice(
            self._in_list_expr,
            self._not_in_list_expr,
            self._is_null_expr,
            self._is_not_null_expr,
            self._comparison_expr,
            self._str_predicate_method,
        ):
            self.pos = save  # the suffix is optional
        return True

    def _literal_in_var_field_expr(self) -> bool:
        """`literal_in_var_field_expr` (:17)."""
        return self._seq(
            self._literal_single,
            self._ws_plus,
            "in",
            self._ws_plus,
            self._var_field_with_func,
        )

    def _literal_not_in_var_field_expr(self) -> bool:
        """`literal_not_in_var_field_expr` (:21)."""
        return self._seq(
            self._literal_single,
            self._ws_plus,
            "not",
            self._ws_plus,
            "in",
            self._ws_plus,
            self._var_field_with_func,
        )

    def _literal_cmp_var_field_expr(self) -> bool:
        """`literal_cmp_var_field_expr` (:26-33) — the Yoda forms.

        Only `==` / `!=` take any `literal_single` on the left; the ordering
        operators take a `number_literal` only.
        """

        def yoda(left, operator: str) -> bool:
            return self._seq(
                left,
                lambda: (self._ws_star(), True)[1],
                operator,
                lambda: (self._ws_star(), True)[1],
                self._var_field_with_func,
            )

        return self._choice(
            lambda: yoda(self._literal_single, "=="),
            lambda: yoda(self._literal_single, "!="),
            lambda: yoda(self._number_literal, "<"),
            lambda: yoda(self._number_literal, ">"),
            lambda: yoda(self._number_literal, "<="),
            lambda: yoda(self._number_literal, ">="),
        )

    def _paren_expr(self) -> bool:
        """`paren_expr` (:15) — parentheses wrap a BOOLEAN sub-expression only,
        never an operand, which is why `var.count == (2)` is not derivable."""
        return self._seq(
            "(",
            lambda: (self._ws_star(), True)[1],
            self._or_expr,
            lambda: (self._ws_star(), True)[1],
            ")",
        )

    def _expr(self) -> bool:
        """`expr` (:11) — the ordered choice, `bool_literal_expr` last."""
        return self._choice(
            self._paren_expr,
            lambda: self._at("c.this_doc()"),
            lambda: self._seq(
                "search(",
                self._string_literal,
                ",",
                lambda: (self._ws_star(), True)[1],
                self._var_field_with_func,
                ")",
            ),
            self._var_field_op_expr,
            self._literal_in_var_field_expr,
            self._literal_not_in_var_field_expr,
            self._literal_cmp_var_field_expr,
            self._boolean_literal,
        )

    def _not_expr(self) -> bool:
        """`not_expr` (:12) — the body is `expr`, NOT `not_expr`, so `not` does
        not chain: `not not x` is not derivable."""
        return self._seq("not", self._ws_plus, self._expr)

    def _operand(self) -> bool:
        """`(expr | not_expr)` as it appears in `and_expr` (:8)."""
        return self._choice(self._expr, self._not_expr)

    def _and_expr(self) -> bool:
        """`and_expr` (:8) — `and` sits between `ws+` on both sides."""
        if not self._operand():
            return False
        while True:
            save = self.pos
            if not self._seq(self._ws_plus, "and", self._ws_plus, self._operand):
                self.pos = save
                return True

    def _or_expr(self) -> bool:
        """`or_expr` (:5) — `or` sits between `ws+` on both sides."""
        if not self._and_expr():
            return False
        while True:
            save = self.pos
            if not self._seq(self._ws_plus, "or", self._ws_plus, self._and_expr):
                self.pos = save
                return True

    def accepts(self) -> bool:
        """`start` (:3) — `SOI ~ ws* ~ or_expr ~ ws* ~ EOI`.

        The trailing EOI is what refuses a comment: pest has no comment rule,
        so `# …` is simply text the grammar cannot consume.
        """
        self._ws_star()
        if not self._or_expr():
            return False
        self._ws_star()
        return self.pos == len(self.text)


def _check_grammar(text: str) -> None:
    """Refuse anything ubCode's own grammar would not derive.

    Runs BEFORE :func:`ast.parse`, so a spelling Python would normalise away
    never reaches the tree.
    """
    if not _PestRecogniser(text).accepts():
        msg = (
            "this is not a condition the shared grammar can read. It is a "
            "deliberately small language — comparisons, `in` / `not in`, "
            "`is None` / `is not None`, `.startswith(…)` / `.endswith(…)`, "
            "`and` / `or` / `not` with parentheses, `var.*` access and the "
            "literals `True` / `False` — and its spelling is fixed: the word "
            "operators need whitespace around them (comparison operators do "
            "not), there are no comments, no tuples, no trailing commas, no "
            "parentheses around an operand, no doubled `not`, and numerals are "
            "decimal with no base prefix and no `_` separators. Every reader "
            "of this file must agree on which files a rule gates, so a "
            "spelling only some of them accept is refused rather than guessed"
        )
        raise VariantConditionError(msg)


# ---------------------------------------------------------------------------
# The one MIRRORED spelling: string escapes
# ---------------------------------------------------------------------------
#
# Not a refusal, so the recogniser cannot own it: ubCode ACCEPTS every escape
# and merely DECODES a smaller set than Python does. Its
# `common.rs::process_escape_sequences` knows `\n \t \r \b \f \v \a \0 \\ \' \"`
# and leaves everything else with its backslash attached, so `'a\x41b'` is six
# characters there and four here. Refusing would be a divergence of its own, so
# the literal is re-decoded ubCode's way and written back onto the tree — which
# keeps the interpreter a pure function of the tree.

#: The escapes `process_escape_sequences` decodes; everything else keeps its
#: backslash, which is where it parts company with Python.
_UBCODE_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "a": "\a",
    "0": "\0",
    "\\": "\\",
    "'": "'",
    '"': '"',
}


def _ubcode_unescape(raw: str) -> str:
    """Decode a string literal's body the way ubCode's lexer does."""
    if "\\" not in raw:
        return raw
    out: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char != "\\" or index + 1 >= len(raw):
            out.append(char)
            index += 1
            continue
        following = raw[index + 1]
        decoded = _UBCODE_ESCAPES.get(following)
        out.append(decoded if decoded is not None else "\\" + following)
        index += 2
    return "".join(out)


def _mirror_string_literals(text: str, node: ast.AST) -> None:
    """Rewrite every string literal to the value ubCode's lexer would read."""
    for child in ast.walk(node):
        if not isinstance(child, ast.Constant) or not isinstance(child.value, str):
            continue
        segment = ast.get_source_segment(text, child)
        if segment is None:
            continue
        body = segment.strip()
        if len(body) >= _SHORTEST_QUOTED and body[0] in "'\"":
            child.value = _ubcode_unescape(body[1:-1])


def validate(expr: str) -> ast.expr:
    """Parse and whitelist-check a rule condition.

    :param expr: The condition exactly as written in ``if = "…"``.
    :return: The validated expression node, ready for :func:`interpret`.
    :raises VariantConditionError: If the condition is outside the grammar.
    """
    text = expr.strip()
    if not text:
        msg = "the condition is empty"
        raise VariantConditionError(msg)
    # Gate one: would ubCode's own grammar derive this text at all? Runs BEFORE
    # `ast.parse`, so a spelling Python's tokenizer would normalise away never
    # reaches the tree.
    _check_grammar(text)
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        msg = f"syntax error: {exc.msg}"
        raise VariantConditionError(msg) from exc
    except (ValueError, MemoryError) as exc:  # pragma: no cover - pathological
        msg = f"the condition could not be parsed: {exc}"
        raise VariantConditionError(msg) from exc
    try:
        # Gate two: kinds and semantics, which the grammar does not constrain —
        # a bare `var.debug` is derivable in pest and refused by ubCode's own
        # DNF whitelist, exactly as it is here.
        _validate_boolean(text, tree.body)
        _mirror_string_literals(text, tree.body)
    except RecursionError as exc:
        # A deeply nested condition (`not not not …`) blows the walk's stack.
        # The module's discipline is that no input reaches an unhandled
        # outcome, so it becomes an ordinary configuration error.
        msg = "the condition is nested too deeply to interpret"
        raise VariantConditionError(msg) from exc
    return tree.body


# ---------------------------------------------------------------------------
# TABLE 2 — the comparison semantics
# ---------------------------------------------------------------------------
#
# ubCode lowers every variant value to a `FilterValue` and every literal to a
# `UbQueryLiteral`, then decides by an explicit type-pair table
# (`rust/ubc_query/src/filter.rs`). A pair with no arm is FALSE, not an error,
# and a handful of shapes raise instead. Both behaviours are reproduced here;
# neither is Python's.
#
# Value lowering (`rust/ubc_config/src/needs/variant_data.rs`
# `variant_value_to_filter`):
#
#   scalar  -> str | bool | int | float
#   array   -> list[str] | list[bool] | list[int] | list[float]
#              (an EMPTY array lowers to an empty list of STRINGS)
#   mapping -> bool(non-empty)      <- a map is compared by its TRUTHINESS
#
# Equality (`value_matches_literal`, filter.rs:440-462). `!=` is its negation:
#
#   (str, str) (bool, bool) (int, int) (float, float)   -> ==
#   (int, float) -> float(v) == l        (float, int) -> v == float(l)
#   ANY OTHER PAIR                                     -> False
#
#   so (bool, int) is FALSE: `var.debug == 0` is false with `debug = false`,
#   where Python says True. This is the divergence that most changes a
#   document set, and its `!=` twin is `var.debug != 0` -> TRUE here, False in
#   Python.
#
# Field vs field (`EqualVariable`, filter.rs:119-139): the right value is
# converted to a literal first, and a LIST cannot be — that raises. So
# `var.tags == var.build.features` is an EVALUATION ERROR, not `False`.
#
# Ordering (`value_compares_number`, filter.rs:464-500): the left value must be
# int or float, else it RAISES; a field on the right must be int or float, else
# it raises. `var.debug > 0` raises here and is `False` in Python.
#
# Membership, literal in field (`LiteralInVarField`, filter.rs:184-253):
#
#   str        + str literal        -> substring
#   list[str]  + str literal        -> contains
#   list[bool] + bool literal       -> contains
#   list[int]  + int literal        -> contains
#   list[int]  + float literal      -> any(float(i) == l)
#   list[float]+ float literal      -> contains
#   list[float]+ int literal        -> any(f == float(l))
#   any other literal for a list    -> RAISES
#   bool | int | float value        -> RAISES  (a mapping lowers to bool, so
#                                     `'debug' in var.build` RAISES too)
#
# Membership, field in list literal (`VarInLiteralList`, filter.rs:288-312):
#   any(equality table) over the literals; a list value matches nothing.
#
# `is None` / `is not None`: variant data can never hold a null, so a
# resolvable key is never None. An unknown key raises, as everywhere else.
#
# `.upper()` / `.lower()` and the string predicates require a str value and
# raise otherwise (`apply_function`, filter.rs:19-42).

#: The shortest a quoted string literal can be: two quote characters.
_SHORTEST_QUOTED = 2

#: Constant kinds, most specific first — ``bool`` before ``int``, because
#: ``isinstance(True, int)`` is true in Python and the two are DIFFERENT kinds
#: in the semantics table (``(bool, int)`` has no arm).
_CONSTANT_KINDS: tuple[tuple[str, type], ...] = (
    ("bool", bool),
    ("int", int),
    ("float", float),
)

_LIST_KINDS = {"list_str", "list_bool", "list_int", "list_float"}
_NUMBER_KINDS = ("int", "float")


def _lower_list(value: list[Any]) -> tuple[str, Any]:
    """Lower an array. Its FIRST element decides the kind, and an EMPTY array
    lowers to an empty list of strings — both straight from ubCode's
    ``array_to_filter``."""
    if not value:
        return ("list_str", [])
    first = value[0]
    if isinstance(first, bool):
        return ("list_bool", [item for item in value if isinstance(item, bool)])
    if isinstance(first, str):
        return ("list_str", [item for item in value if isinstance(item, str)])
    if isinstance(first, int):
        return (
            "list_int",
            [
                item
                for item in value
                if isinstance(item, int) and not isinstance(item, bool)
            ],
        )
    return ("list_float", [item for item in value if isinstance(item, float)])


def _lower(value: Any) -> tuple[str, Any]:
    """Lower a variant value the way ubCode's ``variant_value_to_filter`` does."""
    if isinstance(value, dict):
        # A mapping is compared by its truthiness, exactly as ubCode does it.
        return ("bool", bool(value))
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, float):
        return ("float", value)
    if isinstance(value, str):
        return ("str", value)
    if isinstance(value, list):
        return _lower_list(value)
    msg = f"unsupported variant value of type {type(value).__name__}"
    raise VariantEvalError(msg)


def _matches_literal(value: tuple[str, Any], literal: tuple[str, Any]) -> bool:
    """TABLE 2's equality row. Any pair without an arm is ``False``."""
    kind, payload = value
    lkind, lvalue = literal
    if kind == lkind and kind in {"str", "bool", "int", "float", "null"}:
        return bool(payload == lvalue)
    if kind == "int" and lkind == "float":
        return float(payload) == lvalue
    if kind == "float" and lkind == "int":
        return payload == float(lvalue)
    return False


def _as_literal(value: tuple[str, Any], name: str) -> tuple[str, Any]:
    """Convert a field's value into a literal for a field-vs-field equality."""
    kind, _payload = value
    if kind in _LIST_KINDS:
        msg = f"unsupported type for equality check; `{name}` is a list"
        raise VariantEvalError(msg)
    return value


def _compare_number(
    value: tuple[str, Any], other: float, operator_node: ast.cmpop, name: str
) -> bool:
    """TABLE 2's ordering row. A non-numeric left value RAISES."""
    kind, payload = value
    if kind not in _NUMBER_KINDS:
        msg = f"unsupported type for number comparison; `{name}` is a {kind}"
        raise VariantEvalError(msg)
    left = float(payload)
    if isinstance(operator_node, ast.Lt):
        return left < other
    if isinstance(operator_node, ast.LtE):
        return left <= other
    if isinstance(operator_node, ast.Gt):
        return left > other
    return left >= other


def _literal_in_field(
    value: tuple[str, Any], literal: tuple[str, Any], name: str
) -> bool:
    """TABLE 2's ``literal in field`` row."""
    kind, payload = value
    lkind, lvalue = literal
    if kind == "str":
        if lkind != "str":
            msg = f"unsupported literal type for `in` against the string `{name}`"
            raise VariantEvalError(msg)
        return lvalue in payload
    if kind in _LIST_KINDS:
        return _literal_in_list(kind, payload, literal, name)
    msg = f"unsupported type for `in`; `{name}` is a {kind}"
    raise VariantEvalError(msg)


def _literal_in_list(
    kind: str, payload: list[Any], literal: tuple[str, Any], name: str
) -> bool:
    """The list half of TABLE 2's ``literal in field`` row.

    A literal whose type does not match the array's RAISES rather than
    returning ``False`` — `2 in var.tags` is an evaluation error where Python
    would say ``False``.
    """
    lkind, lvalue = literal
    if kind == "list_str" and lkind == "str":
        return lvalue in payload
    if kind == "list_bool" and lkind == "bool":
        return lvalue in payload
    if kind == "list_int":
        if lkind == "int":
            return lvalue in payload
        if lkind == "float":
            return any(float(item) == lvalue for item in payload)
    if kind == "list_float":
        if lkind == "float":
            return lvalue in payload
        if lkind == "int":
            return any(item == float(lvalue) for item in payload)
    msg = f"unsupported literal type for `in` against the list `{name}`"
    raise VariantEvalError(msg)


def _lookup(node: ast.AST, data: dict[str, Any]) -> Any:
    """Resolve a ``var.*`` attribute chain against the merged mapping."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    parts.reverse()
    current: Any = data
    walked: list[str] = []
    for part in parts:
        walked.append(part)
        if not isinstance(current, dict) or part not in current:
            msg = f"unknown variant data key `var.{'.'.join(walked)}`"
            raise VariantEvalError(msg)
        current = current[part]
    return current


def _transform(node: ast.AST, value: tuple[str, Any], name: str) -> tuple[str, Any]:
    """Apply a ``.upper()`` / ``.lower()`` suffix, raising on a non-string."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return value
    kind, payload = value
    if kind != "str":
        msg = f"unsupported type for `.{node.func.attr}()`; `{name}` is a {kind}"
        raise VariantEvalError(msg)
    return ("str", payload.upper() if node.func.attr == "upper" else payload.lower())


def _receiver_name(node: ast.AST) -> str:
    """The dotted spelling of a receiver's ``var.*`` chain, for a message."""
    chain = _receiver(node)
    return _dotted(chain) if chain is not None else "?"


def _receiver_value(node: ast.AST, data: dict[str, Any]) -> tuple[str, Any]:
    """Resolve and lower a receiver, applying any transformer suffix."""
    chain = _receiver(node)
    if chain is None:  # pragma: no cover - validate() guarantees it
        msg = f"cannot evaluate `{type(node).__name__}`"
        raise VariantEvalError(msg)
    value = _lower(_lookup(chain, data))
    return _transform(node, value, _dotted(chain))


def _evaluate_compare(node: ast.Compare, data: dict[str, Any]) -> bool:
    """Evaluate one comparison through TABLE 2."""
    op = node.ops[0]
    left, right = node.left, node.comparators[0]

    if isinstance(op, _IS_OPS):
        value = _receiver_value(left, data)
        result = value[0] == "null"
        return result if isinstance(op, ast.Is) else not result

    if isinstance(op, _IN_OPS):
        if _receiver(right) is not None:
            container = _receiver_value(right, data)
            literal = (_value_kind(left), _literal_value(left))
            result = _literal_in_field(container, literal, _receiver_name(right))
        else:
            value = _receiver_value(left, data)
            elements = right.elts if isinstance(right, ast.List | ast.Tuple) else []
            result = any(
                _matches_literal(value, (_value_kind(element), _literal_value(element)))
                for element in elements
            )
        return result if isinstance(op, ast.In) else not result

    left_is_receiver = _receiver(left) is not None
    receiver_node = left if left_is_receiver else right
    other_node = right if left_is_receiver else left
    value = _receiver_value(receiver_node, data)
    name = _receiver_name(receiver_node)

    if isinstance(op, _EQ_OPS):
        if _receiver(other_node) is not None:
            other = _as_literal(
                _receiver_value(other_node, data), _receiver_name(other_node)
            )
        else:
            other = (_value_kind(other_node), _literal_value(other_node))
        result = _matches_literal(value, other)
        return result if isinstance(op, ast.Eq) else not result

    # Ordering. `a < b` written the other way round is `b > a`, which is how
    # ubCode canonicalises a Yoda comparison (`literal_cmp_var_field_expr`).
    operator_node: ast.cmpop = op
    if not left_is_receiver:
        operator_node = _FLIPPED[type(op)]()
    if _receiver(other_node) is not None:
        other_value = _receiver_value(other_node, data)
        if other_value[0] not in _NUMBER_KINDS:
            msg = (
                f"unsupported type for number comparison; "
                f"`{_receiver_name(other_node)}` is a {other_value[0]}"
            )
            raise VariantEvalError(msg)
        other_number = float(other_value[1])
    else:
        other_number = float(_literal_value(other_node))
    return _compare_number(value, other_number, operator_node, name)


#: Ordering operators under operand exchange, for a Yoda comparison.
_FLIPPED: dict[type[ast.cmpop], type[ast.cmpop]] = {
    ast.Lt: ast.Gt,
    ast.Gt: ast.Lt,
    ast.LtE: ast.GtE,
    ast.GtE: ast.LtE,
}


def _evaluate_predicate(node: ast.Call, data: dict[str, Any]) -> bool:
    """Evaluate a terminal ``.startswith(…)`` / ``.endswith(…)``."""
    func = node.func
    if not isinstance(func, ast.Attribute):  # pragma: no cover - validated
        msg = "a string predicate may only be called on a `var.*` field"
        raise VariantEvalError(msg)
    receiver = func.value
    value = _receiver_value(receiver, data)
    name = _receiver_name(receiver)
    if value[0] != "str":
        msg = f"unsupported type for a string predicate; `{name}` is a {value[0]}"
        raise VariantEvalError(msg)
    literal = _literal_value(node.args[0])
    if func.attr == "startswith":
        return value[1].startswith(literal)
    return value[1].endswith(literal)


def interpret(node: ast.expr, data: dict[str, Any]) -> bool:
    """Evaluate a validated condition against the merged variant data.

    ``and`` / ``or`` short-circuit left to right, which is what ubCode's DNF
    evaluation does too (measured): an error in an operand that is never
    reached never surfaces.

    The interpreter is a pure function of the validated tree and the data: the
    two questions that need the source text (``-2`` versus ``- 2``, and one
    string literal versus an implicitly concatenated pair) are settled by
    :func:`validate` and cannot be reopened here.

    :param node: The node :func:`validate` returned.
    :param data: The merged variant map — a plain mapping, not a proxy.
    :raises VariantEvalError: On an unknown key or an unsupported type pair.
    """
    try:
        return _interpret(node, data)
    except RecursionError as exc:
        msg = "the condition is nested too deeply to evaluate"
        raise VariantEvalError(msg) from exc


def _interpret(node: ast.AST, data: dict[str, Any]) -> bool:
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_interpret(value, data) for value in node.values)
        return any(_interpret(value, data) for value in node.values)
    if isinstance(node, ast.UnaryOp):
        return not _interpret(node.operand, data)
    if isinstance(node, ast.Compare):
        return _evaluate_compare(node, data)
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.Call):
        return _evaluate_predicate(node, data)
    msg = f"cannot evaluate `{type(node).__name__}`"  # pragma: no cover
    raise VariantEvalError(msg)  # pragma: no cover


def evaluate(expr: str, data: dict[str, Any]) -> bool:
    """Validate and evaluate ``expr`` in one call."""
    return interpret(validate(expr), data)


# ---------------------------------------------------------------------------
# Variant data — a private copy of sphinx-needs' semantics
# ---------------------------------------------------------------------------


def validate_variant_data(data: Any, path: str = "var") -> None:
    """Check that ``data`` has the shape a variant map is allowed to have.

    Keys must be strings; leaves must be ``str`` / ``bool`` / ``int`` /
    ``float``; a list must be empty or uniform-scalar; nested mappings recurse.

    :raises VariantDataError: On any violation, naming the dotted path.
    """
    if not isinstance(data, dict):
        msg = f"{path}: expected a mapping, got {type(data).__name__}"
        raise VariantDataError(msg)
    for key, value in data.items():
        if not isinstance(key, str):
            msg = f"{path}: all keys must be strings, got {type(key).__name__}"
            raise VariantDataError(msg)
        full = f"{path}.{key}"
        if isinstance(value, dict):
            validate_variant_data(value, full)
        elif isinstance(value, list):
            _validate_variant_list(value, full)
        elif not isinstance(value, _SCALAR_TYPES):
            msg = (
                f"{full}: expected str/bool/int/float/list/mapping, "
                f"got {type(value).__name__}"
            )
            raise VariantDataError(msg)


def _validate_variant_list(value: list[Any], full: str) -> None:
    """An array must be empty, or uniform and scalar."""
    if not value:
        return
    first_type = type(value[0])
    if first_type not in _SCALAR_TYPES:
        msg = (
            f"{full}: array elements must be str/bool/int/float, "
            f"got {first_type.__name__}"
        )
        raise VariantDataError(msg)
    for index, item in enumerate(value):
        if type(item) is not first_type:
            msg = (
                f"{full}[{index}]: expected {first_type.__name__}, got "
                f"{type(item).__name__} (arrays must be uniform type)"
            )
            raise VariantDataError(msg)


def load_variant_data_file(path: Path) -> dict[str, Any]:
    """Load a variant-data JSON file and validate its shape.

    JSON only, and the top level must be an object — the same three failures
    sphinx-needs reports (missing file, undecodable JSON, non-object).

    :raises VariantDataError: On any of them.
    """
    if not path.is_file():
        msg = f"variant data file not found: {path}"
        raise VariantDataError(msg)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        msg = f"invalid JSON in {path}: {exc}"
        raise VariantDataError(msg) from exc
    except OSError as exc:  # pragma: no cover - defensive
        msg = f"could not read {path}: {exc}"
        raise VariantDataError(msg) from exc
    if not isinstance(raw, dict):
        msg = (
            f"variant data file must contain a JSON object, "
            f"got {type(raw).__name__}: {path}"
        )
        raise VariantDataError(msg)
    validate_variant_data(raw)
    return raw


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge ``override`` into ``base``; ``override`` wins at the leaves.

    Recurses **only when both sides are mappings**. Everything else is a
    wholesale replacement — a list replaces a list entirely, a scalar replaces
    a mapping and vice versa. That is sphinx-needs' rule, reproduced exactly,
    and it is what makes the merge idempotent (see
    :func:`resolve_variant_data`).
    """
    result = base.copy()
    for key, value in override.items():
        existing = result.get(key)
        if key in result and isinstance(existing, dict) and isinstance(value, dict):
            result[key] = deep_merge(existing, value)
        else:
            result[key] = value
    return result


def resolve_variant_data(
    inline: Any,
    file_ref: Path | None,
) -> dict[str, Any]:
    """Compute the merged variant map: file first, inline deep-merged on top.

    The merge is **unconditional**, and that is the whole trick. Three worlds
    have to give the same answer:

    * sphinx-needs absent — nothing else computes the map, so this is the whole
      computation;
    * sphinx-needs installed but not yet resolving at ``config-inited``
      (every release up to and including 8.3.1) — ``needs_variant_data`` holds
      the *inline* half only, and this supplies the merge it has not performed;
    * sphinx-needs resolving at ``config-inited`` (post-#1787) —
      ``needs_variant_data`` is already merged, and re-merging it is a no-op,
      because ``deep_merge(file, already_merged) == already_merged`` for every
      shape ``deep_merge`` can produce.

    So there is no version sniffing, no import of sphinx-needs and no feature
    detection, and the answer always agrees with whatever sphinx-needs computed.
    ``tests/test_variant_data.py`` pins all three cells plus the idempotency.

    :param inline: The inline mapping (``needs_variant_data`` or the TOML's
        ``[needs.variant_data]`` table). ``None`` and ``{}`` both mean "none".
    :param file_ref: An **already anchored** absolute path, or ``None``. The
        two anchors are the caller's business — see
        :func:`sphinx_mounts.config.load_variant_sources_from_toml`.
    :raises VariantDataError: If the file or the inline mapping is malformed.
    """
    base: dict[str, Any] = {}
    if file_ref is not None:
        base = load_variant_data_file(file_ref)
    if inline:
        validate_variant_data(inline)
    return deep_merge(base, inline or {})
