"""The condition grammar and its semantics, mirrored on ubCode's engine.

The vendored corpus (``test_variant_conditions.py``) pins 46 conditions. It is
the shared contract, and it is not the whole grammar: every form it is silent
about was decided here by whichever engine happened to be reading the string.
Review measured six such forms accepted-and-true here and refused-or-false
there — one rule string, two document sets, which is the exact hazard the
narrowing exists to remove.

So the accept-set AND the comparison semantics are now **bound to ubCode's
shipped engine**, and this module is that binding. Every row below is a
measurement, not a design decision:

* ubCode's grammar comes from ``rust/ubc_query/src/py_expr.pest`` plus the AST
  conversion in ``py_expr.rs``;
* its evaluation comes from ``rust/ubc_query/src/filter.rs`` and the value
  lowering in ``rust/ubc_config/src/needs/variant_data.rs``;
* and every expression here was run through the **shipped engine itself** —
  a scratch binary with a path dependency on ``ubc_config``, calling
  ``UbprojectConfigR::from_toml_str`` for the verdict and
  ``evaluate_if_expression`` for the value, over the corpus's own
  ``[variant_data]``.

The semantics deliberately depart from Python. ``var.debug == 0`` is ``False``
here because it is false there; Python's ``False == 0`` would have made it true
and the two tools would have built different sites from one file, silently. The
same divergence read the other way is ``var.debug != 0``, ``True`` here and
``False`` in Python.

``design/mapping-contract.md`` §12.5 carries both tables for a third reader.
"""

from __future__ import annotations

from typing import Any

import pytest

from sphinx_mounts.variants import (
    VariantConditionError,
    VariantEvalError,
    _PestRecogniser,
    evaluate,
    validate,
)

#: The corpus's own ``[variant_data]``, so a row here can be compared with a
#: corpus row directly.
VARIANT_DATA: dict[str, Any] = {
    "edition": "pro",
    "count": 2,
    "ratio": 1.5,
    "debug": False,
    "name": "Widget",
    "tags": ["alpha", "beta"],
    "build": {"debug": True, "features": ["core", "net"]},
    "empty": {},
}


class _Sentinel:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name


#: The condition is outside ubCode's grammar: a configuration error.
REJECT = _Sentinel("REJECT")
#: The condition is inside the grammar and fails to EVALUATE, which excludes.
ERROR = _Sentinel("ERROR")


def _row_id(row: tuple[str, Any]) -> str:
    return f"{row[1]}:{row[0] or '<empty>'}"


#: Every row measured against ubCode's shipped engine.
#:
#: ``REJECT`` = refused by the grammar; ``ERROR`` = accepted and unevaluable;
#: ``True`` / ``False`` = accepted and that truth value under
#: :data:`VARIANT_DATA`.
UBCODE_TABLE: list[tuple[str, Any]] = [
    ("var.count == 2", True),
    ("var.count == -2", False),
    ("var.count == +2", REJECT),
    ("var.count == 2.0", True),
    ("var.count == True", False),
    ("var.count == None", False),
    ("var.edition == 'pro'", True),
    ("var.tags == ['alpha', 'beta']", REJECT),
    ("var.count == var.ratio", False),
    ("var.name.upper() == 'WIDGET'", True),
    ("var.count == var.name.upper()", False),
    ("var.name.startswith('W') == True", REJECT),
    ("var.debug == 0", False),
    ("var.debug == False", True),
    ("'pro' == var.edition", True),
    ("2 == var.count", True),
    ("2 < var.count", False),
    ("'pro' < var.edition", REJECT),
    ("True == var.debug", False),
    ("None == var.edition", False),
    ("['a'] == var.tags", REJECT),
    ("var.count < 2", False),
    ("var.count <= 2", True),
    ("var.count > 2", False),
    ("var.count >= 2", True),
    ("var.count < 2.5", True),
    ("var.count < -1", False),
    ("var.edition < 'x'", REJECT),
    ("var.count < True", REJECT),
    ("var.count < None", REJECT),
    ("var.count < var.ratio", False),
    ("var.count < var.name", ERROR),
    ("var.name.upper() < 5", ERROR),
    ("var.debug > 0", ERROR),
    ("var.edition in ['pro', 'x']", True),
    ("var.edition in ['pro', 2]", True),
    ("var.edition in 'professional'", REJECT),
    ("var.edition in var.name", REJECT),
    ("var.edition not in var.name", REJECT),
    ("'net' in var.build.features", True),
    ("'net' not in var.build.features", False),
    ("'debug' in var.build", ERROR),
    ("'x' in var.build", ERROR),
    ("2 in var.tags", ERROR),
    ("var.tags in var.build.features", REJECT),
    ("var.count in [1, 2, 3]", True),
    ("var.debug in [True, False]", True),
    ("None in var.tags", ERROR),
    ("'a' in 'abc'", REJECT),
    ("var.edition is None", False),
    ("var.edition is not None", True),
    ("var.missing is None", ERROR),
    ("var.build is None", False),
    ("var.empty is None", False),
    ("var.name.startswith('Wid')", True),
    ("var.name.endswith('get')", True),
    ("var.name.upper().startswith('WID')", True),
    ("var.count.startswith('2')", ERROR),
    ("not var.name.startswith('Wid')", False),
    ("True == True", REJECT),
    ("'a' == 'b'", REJECT),
    ("1 < 2", REJECT),
    ("True", True),
    ("False", False),
    ("not True", False),
    ("var.debug", REJECT),
    ("not var.debug", REJECT),
    ("var.build == var.empty", False),
    ("var.build == 'x'", False),
    ("var.tags == var.build.features", ERROR),
    ("var.tags != var.build.features", ERROR),
    ("var.build.debug == var.debug", False),
    ("len(var.tags) > 1", REJECT),
    ("var.name == 'Wid' 'get'", REJECT),
    ("-var.count == 2", REJECT),
    ("var.count == - 2", REJECT),
    ("var.ratio == 1", False),
    ("var.ratio == 1.5", True),
    ("var.tags != ['alpha', 'beta']", REJECT),
    ("var.missing == 'x'", ERROR),
    ("var.build.missing == 1", ERROR),
    ("var.ratio == -1.5", False),
    ("var.count == -0", False),
    ("var.count != 2", False),
    ("var.count != 3", True),
    ("var.edition != 'pro'", False),
    ("var.debug != 0", True),
    ("var.count != True", True),
    ("var.build.features == ['core', 'net']", REJECT),
    ("'ph' in var.edition", False),
    ("'PRO' in var.edition.upper()", True),
    ("var.edition.upper() in ['PRO']", True),
    ("var.empty == var.empty", True),
    ("var.build == var.build", True),
    ("var.build != var.empty", True),
    ("1 < var.count < 3", REJECT),
    ("var.count == 2 and var.debug == False", True),
    ("(var.count == 2)", True),
    ("var.name.lower() == 'widget'", True),
    ("var.tags == 'alpha'", False),
    ("'x' in var.count", ERROR),
    ("var.count in var.tags", REJECT),
    ("var.name.startswith('W') and var.count == 2", True),
    ("not var.name.upper()", REJECT),
    ("var.name.upper()", REJECT),
    ("var.count == 2e1", False),
    ("var.ratio == 1.5e0", True),
    ("var.tags == []", REJECT),
    ('var.name.startswith("W")', True),
    ('var.edition == "pro"', True),
    ("var.count >= -2", True),
    ("var.build.features in ['core']", False),
    ("var.empty in ['x']", False),
    ("'alpha' in var.tags", True),
    ("True in var.tags", ERROR),
    ("var.debug is None", False),
    ("var.debug is not None", True),
    ("var.count.upper() == 'X'", ERROR),
    ("var.name.upper().upper() == 'X'", REJECT),
    ("var.name.endswith('get') == True", REJECT),
    ("var.tags != 'alpha'", True),
    ("var.build.debug != var.debug", True),
    ("var.count == var.count", True),
    ("var.ratio == var.count", False),
    ("2.0 == var.count", True),
    ("2 != var.count", False),
    ("'net' in var.tags", False),
    ("var.count == 2 or var.tags == var.build.features", True),
    ("var.tags == var.build.features or var.count == 2", ERROR),
    ("var.count == 3 and var.tags == var.build.features", False),
    ("var.tags == var.build.features and var.count == 3", ERROR),
    ("var.count == 2 or var.missing == 'x'", True),
    ("var.missing == 'x' or var.count == 2", ERROR),
    ("var.count == 3 and var.missing == 'x'", False),
    ("False and var.missing == 'x'", False),
    ("True or var.missing == 'x'", True),
    ("not (var.count == 2)", False),
    ("var.count == 2 and (var.debug == False or var.missing == 'x')", True),
]


#: The LEXICAL layer, measured the same way.
#:
#: The kind-level table above is necessary and not sufficient: ubCode's lexer
#: refuses spellings Python's tokenizer normalises away, and every one of them
#: was in the LEAK direction — ubCode refuses (so the rule is permanently false
#: and its files are EXCLUDED) while an AST-only reader evaluates and keeps
#: them. `var.edition in ['pro',]` and `not(var.edition == 'basic')` are not
#: exotic: a trailing comma is what most formatters produce, and `not(` is how
#: a great many people write a negation.
#:
#: The accepted rows matter as much as the refused ones. Where pest is
#: whitespace-tolerant we are identically tolerant — `var.count>=2`,
#: `[ 'pro' , 'x' ]`, doubled spaces and tabs are all fine — so this is parity
#: rather than a blanket tightening.
LEXICAL_TABLE: list[tuple[str, Any]] = [
    ("not(var.edition == 'basic')", REJECT),
    ("not (var.edition == 'basic')", True),
    ("not  var.debug == False", False),
    ("var.count == 2 and(var.debug == False)", REJECT),
    ("var.count == 2 and (var.debug == False)", True),
    ("var.edition=='pro'and var.count==2", REJECT),
    ("var.count == 2and var.debug == False", REJECT),
    ("var.count == 2 and var.debug == False", True),
    ("(var.count == 2)or(var.debug == False)", REJECT),
    ("(var.count == 2) or (var.debug == False)", True),
    ("var.edition in['pro']", REJECT),
    ("var.edition in ['pro']", True),
    ("var.edition not in['x']", REJECT),
    ("'net'in var.build.features", REJECT),
    ("var.edition is None", False),
    ("var.edition isNone", REJECT),
    ("var.name.upper( ) == 'WIDGET'", REJECT),
    ("var.name.upper () == 'WIDGET'", REJECT),
    ("var.name.upper() == 'WIDGET'", True),
    ("var.name.startswith( 'Wid' )", REJECT),
    ("var.name.startswith('Wid' )", REJECT),
    ("var.name.startswith( 'Wid')", REJECT),
    ("var.name.startswith('Wid')", True),
    ("var . name == 'Widget'", REJECT),
    ("var. name == 'Widget'", REJECT),
    ("var .name == 'Widget'", REJECT),
    ("var.name .startswith('Wid')", REJECT),
    ("var.build .debug == True", REJECT),
    ("var.edition in ['pro',]", REJECT),
    ("var.edition in ['pro','x',]", REJECT),
    ("var.edition in ['pro' ,]", REJECT),
    ("var.edition in ['pro' , 'x']", True),
    ("var.edition in [ 'pro' ]", True),
    ("var.edition in ('pro','x')", REJECT),
    ("var.edition in ('pro',)", REJECT),
    ("var.name.startswith('Wid',)", REJECT),
    ("var.count == 0x2", REJECT),
    ("var.count == 0X2", REJECT),
    ("var.count == 0b10", REJECT),
    ("var.count == 0o2", REJECT),
    ("var.count == 2_0", REJECT),
    ("var.count == 1_0", REJECT),
    ("var.ratio == .5", REJECT),
    ("var.count == 02", REJECT),
    ("var.count == 2.", True),
    ("var.count == 2e1", False),
    ("var.count == 2E1", False),
    ("var.ratio == 1.5e0", True),
    ("var.count == +0", REJECT),
    ("var.name == 'Widge\\x74'", False),
    ("var.name == 'Widget'", True),
    ("var.name.startswith('W\\x69')", False),
    ("var.name.startswith('W\\151')", False),
    ("var.name.endswith('ge\\x74')", False),
    ("var.name == 'Widge\\164'", False),
    ("var.name == 'Wid\\get'", False),
    ('var.name == "Widget"', True),
    ("var.name != 'a\\nb'", True),
    ("var.name != 'a\\tb'", True),
    ("var.name != 'a\\\\b'", True),
    ("var.name != 'a\\'b'", True),
    ("var.edition=='pro'", True),
    ("var.count>=2", True),
    ("var.count >= 2", True),
    ("var.edition == 'pro'  and  var.count == 2", True),
    ("var.name.upper()  ==  'WIDGET'", True),
    ("var.name == 'a\\u0041b'", False),
    ("var.count == 2.5e-1", False),
    ("var.count == -0x2", REJECT),
    ("var.edition == 'pro'\tand\tvar.count == 2", True),
    ("var.edition\t==\t'pro'", True),
    # Four further classes, found only after the enumerated refusals were in
    # place — which is the evidence that enumeration does not converge, and the
    # reason the spelling gate is now a port of the sibling grammar rather than
    # a list. Every one of these was in the LEAK direction before that port.
    #
    #   comments  — the reachable one: `if = "var.edition == 'pro'  # pro only"`
    #               is an ordinary thing to write, and TOML passes the `#`
    #               through a quoted string verbatim. That grammar has no
    #               comment rule; Python's tokenizer strips it before an AST
    #               exists.
    #   not not   — `not` does not chain there: its body is an `expr`, and a
    #               `not_expr` is not one. Parenthesised, it does chain.
    #   ( operand ) — parentheses wrap a boolean sub-expression only, never an
    #               operand; Python's AST discards them entirely.
    #   NFKC      — Python folds identifiers, so a fullwidth n resolves the
    #               real `name` key; that grammar's field names are ASCII.
    ("var.count == 2 # trailing comment", REJECT),
    ("var.count == 2#c", REJECT),
    ("var.count == 2 and var.debug == False # c", REJECT),
    ("var.count == 2 # 'quoted # hash'", REJECT),
    ("var.count == 2 #", REJECT),
    ("not not var.count == 2", REJECT),
    ("not not not var.count == 2", REJECT),
    ("var.count == (2)", REJECT),
    ("var.count == ((2))", REJECT),
    ("var.edition in (['pro'])", REJECT),
    ("var.ｎame == 'Widget'", REJECT),  # noqa: RUF001 - fullwidth, deliberately
    ("var.naᵐe == 'Widget'", REJECT),
    ("not (not (var.count == 2))", True),
    ("not (var.count == 2)", False),
    ("var.café == 'x'", REJECT),
    ("var.name == 'a#b'", False),
    ("var.name == 'a and b'", False),
]


# The table deliberately carries escapes Python calls invalid; that IS the
# divergence being pinned.
@pytest.mark.filterwarnings("ignore::SyntaxWarning")
@pytest.mark.parametrize("row", LEXICAL_TABLE, ids=_row_id)
def test_matches_ubcodes_lexer(row: tuple[str, Any]) -> None:
    """Reproduce one measured LEXICAL row of ubCode's shipped engine.

    Same instrument as the table above: each spelling was run through the
    engine itself and its verdict recorded here.
    """
    expr, expected = row
    if expected is REJECT:
        with pytest.raises(VariantConditionError):
            validate(expr)
        return
    validate(expr)
    if expected is ERROR:
        with pytest.raises(VariantEvalError):
            evaluate(expr, VARIANT_DATA)
        return
    assert evaluate(expr, VARIANT_DATA) is expected


def test_a_string_literal_is_decoded_ubcodes_way() -> None:
    """``\\x41`` is a literal backslash-x-4-1 there and an ``A`` in Python.

    ubCode's ``process_escape_sequences`` knows ``\\n \\t \\r \\b \\f \\v \\a \\0 \\\\ \\' \\"``
    and leaves every other escape with its backslash attached. It ACCEPTS the
    spelling, so refusing it here would be a divergence of its own — instead
    the literal is re-decoded its way and written back onto the tree, which
    keeps the interpreter a pure function of the tree and makes the two engines
    compare the same characters.
    """
    assert evaluate("var.name == 'Widge\\x74'", VARIANT_DATA) is False
    assert evaluate("var.name == 'Widget'", VARIANT_DATA) is True
    # The escapes both engines decode identically still work.
    assert evaluate("var.name != 'a\\nb'", VARIANT_DATA) is True
    assert evaluate("var.name != 'a\\\\b'", VARIANT_DATA) is True


def test_the_lexical_table_covers_every_measured_class() -> None:
    """A guard against the table being trimmed to whatever happens to pass."""
    text = " ".join(expr for expr, _ in LEXICAL_TABLE)
    for spelling in (
        "not(",
        "and(",
        ")or(",
        "in[",
        "2and",
        "upper( )",
        "var . ",
        "',]",
        "('pro'",
        "0x2",
        "0b10",
        "2_0",
        ".5",
        "\\x74",
        # The four classes found after the enumerated refusals were in place.
        "# trailing comment",
        "not not ",
        "== (2)",
        "ｎame",  # noqa: RUF001 - fullwidth, deliberately
    ):
        assert spelling in text, spelling
    assert len(LEXICAL_TABLE) >= 80


def test_the_grammar_gate_is_a_port_not_an_enumeration() -> None:
    """The property that makes the class finite, asserted structurally.

    Two rounds of review each produced a fresh spelling that an enumeration of
    refusals had no rule for. What closes it is that the spelling gate now
    *derives* — it accepts exactly what the sibling grammar derives and refuses
    everything else, whether or not anyone thought of it.

    So this test does not check a list. It takes spellings nobody enumerated
    and asserts they are refused because the grammar cannot produce them.
    """
    for unheard_of in (
        "var.count == 2 ;",
        "var.count == 2 if True else False",
        "var.count == 0_2",
        "var.count == 2\\",
        "var.count == 2 ]",
        "var.name == 'x' 'y' 'z'",
        "var.name == r'x'",
        "var.name == f'x'",
        "var.name == b'x'",
        "lambda: var.count == 2",
        "var.count == 2 == 2",
        "var[0] == 2",
        "var.count == 2 and",
        "and var.count == 2",
        "() == var.count",
        "var.count == {1}",
        "var.count == 2 % 3",
    ):
        assert not _PestRecogniser(unheard_of).accepts(), unheard_of
        with pytest.raises(VariantConditionError):
            validate(unheard_of)


def test_the_recogniser_does_not_over_refuse() -> None:
    """The fix's natural failure mode: refusing what the sibling ACCEPTS.

    A blanket tightening would look identical to parity on the leak axis and
    be a divergence in the other direction — a project that builds there and
    aborts here. Every spelling below was measured accepted by that engine.
    """
    for accepted in (
        "var.count>=2",
        "var.edition=='pro'",
        "var.edition == 'pro'  and  var.count == 2",
        "var.edition\t==\t'pro'",
        "var.edition in [ 'pro' , 'x' ]",
        "not (var.count == 2)",
        "not (not (var.count == 2))",
        "(var.count == 2) or (var.debug == False)",
        "var.count == 2.",
        "var.count == 2e1",
        "var.ratio == 2.5e-1",
        "var.count == -2",
        "var.name.upper().startswith('WID')",
        "'net' in var.build.features",
        "var.name == 'a and b'",
        "var.name == 'a#b'",
        "var.edition is not None",
        "len(var.tags) > 1",
        "search('pro', var.edition)",
        "c.this_doc()",
        "var.debug",
        # A dotted `upper` with no parentheses is an ordinary field path —
        # the `!("(")` lookahead only excludes a segment a call follows.
        # Probed: ACCEPT.
        "var.count.upper == 'X'",
        "var.a.b.c == 1",
    ):
        assert _PestRecogniser(accepted).accepts(), accepted


@pytest.mark.parametrize("row", UBCODE_TABLE, ids=_row_id)
def test_matches_ubcodes_engine(row: tuple[str, Any]) -> None:
    """Reproduce one measured row of ubCode's shipped engine.

    A disagreement here is not a style difference: it is a spelling that puts
    a different set of files in the two tools' builds from one ``if`` string.
    """
    expr, expected = row
    if expected is REJECT:
        with pytest.raises(VariantConditionError):
            validate(expr)
        return
    validate(expr)
    if expected is ERROR:
        with pytest.raises(VariantEvalError):
            evaluate(expr, VARIANT_DATA)
        return
    assert evaluate(expr, VARIANT_DATA) is expected


def test_the_table_covers_every_operator_and_operand_kind() -> None:
    """A cheap guard against the table being trimmed to what happens to pass.

    The enumeration is what makes this a contract rather than a sample: the
    corpus's holes were exactly the operand/operator combinations nobody had
    written down.
    """
    text = " ".join(expr for expr, _ in UBCODE_TABLE)
    for operator in ("==", "!=", "<=", ">=", " < ", " > ", " in ", "not in", "is None"):
        assert operator in text, operator
    for operand in ("-2", "2.0", "True", "None", "['", ".upper()", ".startswith("):
        assert operand in text, operand
    assert len(UBCODE_TABLE) >= 100


# ---------------------------------------------------------------------------
# The divergences from Python, called out one at a time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expr", "ours", "python"),
    [
        ("var.debug == 0", False, True),
        ("var.debug != 0", True, False),
        ("var.debug > 0", ERROR, False),
        ("var.tags == var.build.features", ERROR, False),
        ("var.tags != var.build.features", ERROR, True),
        ("'debug' in var.build", ERROR, True),
        ("2 in var.tags", ERROR, False),
        ("None in var.tags", ERROR, False),
        ("var.build == var.build", True, True),
    ],
    ids=lambda value: str(value),
)
def test_the_semantics_are_ubcodes_not_pythons(
    expr: str, ours: Any, python: Any
) -> None:
    """Each row is a place where matching CPython would split the document set.

    ``python`` is what Python's own operators return for the same expression
    over the same data — recorded so that a future reader can see the size of
    the deliberate departure rather than having to re-derive it, and so that
    ubCode's published claim that these "match Python's semantics"
    (``docs/source/usage/variants.rst``) is visibly a defect in ITS docs rather
    than something this reader adopted.
    """
    if ours is ERROR:
        with pytest.raises(VariantEvalError):
            evaluate(expr, VARIANT_DATA)
    else:
        assert evaluate(expr, VARIANT_DATA) is ours
    assert python is not None  # the Python column is documentation, not a call


def test_and_or_short_circuit_left_to_right() -> None:
    """Measured on ubCode: an unreached operand's error never surfaces.

    ubCode evaluates a DNF, which is not obviously left-to-right — so this was
    probed rather than assumed. Both engines agree.
    """
    assert evaluate("var.count == 2 or var.missing == 'x'", VARIANT_DATA) is True
    assert evaluate("var.count == 3 and var.missing == 'x'", VARIANT_DATA) is False
    with pytest.raises(VariantEvalError):
        evaluate("var.missing == 'x' or var.count == 2", VARIANT_DATA)


def test_a_negative_literal_must_hug_its_digits() -> None:
    """``-2`` is one literal in ubCode's grammar; ``- 2`` and ``+2`` are not.

    Python's AST gives ``-2`` and ``- 2`` the same tree, so the column offsets
    are what separate them. Without that, accepting negatives would also accept
    two spellings ubCode refuses.
    """
    validate("var.count == -2")
    for refused in ("var.count == - 2", "var.count == +2", "-var.count == 2"):
        with pytest.raises(VariantConditionError):
            validate(refused)


def test_implicit_string_concatenation_is_refused() -> None:
    """Python folds ``'Wid' 'get'`` at parse time; ubCode has no such rule.

    The folded constant evaluates TRUE where ubCode refuses the condition
    outright, so the source segment is read back to tell the two apart.
    """
    with pytest.raises(VariantConditionError, match="shared grammar can read"):
        validate("var.name == 'Wid' 'get'")
    validate("var.name == 'Widget'")


def test_a_transformer_may_carry_a_predicate() -> None:
    """``var.name.upper().startswith('WID')`` is accepted — measured.

    One transformer, then a predicate. A second transformer is not:
    ``var_field_with_func`` admits exactly one function.
    """
    assert evaluate("var.name.upper().startswith('WID')", VARIANT_DATA) is True
    with pytest.raises(VariantConditionError):
        validate("var.name.upper().upper() == 'X'")


def test_recursion_is_an_ordinary_error_not_a_traceback() -> None:
    """No input reaches an unhandled outcome — including a pathological one."""
    deep = "not " * 4000 + "var.count == 2"
    with pytest.raises((VariantConditionError, VariantEvalError)):
        evaluate(deep, VARIANT_DATA)
