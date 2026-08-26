"""The rule-condition grammar, held to the shared conformance corpus.

``tests/fixtures/variant_condition_conformance.toml`` is a vendored,
byte-identical copy of ubCode's canonical corpus (source commit recorded in its
header). It is the **contract** for the ``[[source.variant_sources]]`` ``if``
grammar: a narrowed grammar only removes the "one rule string, two document
sets" hazard if both engines refuse the same forms, and prose cannot enforce
that across two repositories on independent release cadences.

Two things are asserted here and both matter:

* every row's verdict, and for an accepted row its truth value (or that it is
  an *evaluation* error rather than a grammar error);
* the number of rows, so a truncated or silently-trimmed vendor is a red test
  rather than quietly reduced coverage.
"""

from __future__ import annotations

from pathlib import Path
import tomllib
from typing import Any

import pytest

from sphinx_mounts.variants import (
    VariantConditionError,
    VariantEvalError,
    evaluate,
    validate,
)

CORPUS_PATH = Path(__file__).parent / "fixtures" / "variant_condition_conformance.toml"

#: The number of ``[[case]]`` rows the vendored corpus is expected to carry.
#:
#: Pinned so that a vendored copy that lost rows — a truncated download, a
#: merge that dropped a hunk, a "tidy-up" — fails loudly. Raising it is the
#: normal consequence of re-vendoring a corpus that grew upstream; lowering it
#: needs a reason in the commit message.
EXPECTED_CASE_COUNT = 103

#: Modules that must stay importable outside sphinx-mounts entirely.
DEPENDENCY_FREE_MODULES = ("variants.py", "dialect.py")


def _corpus() -> dict[str, Any]:
    with CORPUS_PATH.open("rb") as handle:
        return tomllib.load(handle)


CORPUS = _corpus()
VARIANT_DATA: dict[str, Any] = CORPUS["variant_data"]
CASES: list[dict[str, Any]] = CORPUS["case"]


def _case_id(case: dict[str, Any]) -> str:
    expr = case["expr"] or "<empty>"
    return f"{case['verdict']}:{expr}"


def test_the_corpus_still_has_every_row() -> None:
    """A truncated vendor is a red test, not reduced coverage."""
    assert len(CASES) == EXPECTED_CASE_COUNT, (
        f"{CORPUS_PATH.name} carries {len(CASES)} cases, expected "
        f"{EXPECTED_CASE_COUNT}. Re-vendoring a grown corpus means bumping "
        f"EXPECTED_CASE_COUNT; anything else means rows were lost."
    )


def test_the_corpus_header_records_its_provenance() -> None:
    """The vendored header must keep naming where the canonical copy lives.

    Without it the file reads as something this repository authored, and the
    next person to "fix" a failing row edits the contract instead of the
    implementation.
    """
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert "rust/ubc_config/tests/fixtures/variant_condition_conformance.toml" in header
    assert "1388b3528686" in header
    assert "CANONICAL" in header


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_conformance_row(case: dict[str, Any]) -> None:
    """Reproduce one corpus row.

    Three shapes, exactly as the corpus header defines them:

    * ``verdict = "reject"`` — a configuration error, refused by ``validate``;
    * ``verdict = "accept"`` with ``value`` — accepted and evaluating to that
      truth value against ``[variant_data]``;
    * ``verdict = "accept"`` with ``error = true`` — accepted by the grammar,
      failing to evaluate (an unknown key), which excludes the rule's files.
    """
    expr: str = case["expr"]
    why: str = case["why"]
    if case["verdict"] == "reject":
        with pytest.raises(VariantConditionError):
            validate(expr)
        return
    # Accepted by the grammar, whatever happens at evaluation time.
    validate(expr)
    if case.get("error"):
        with pytest.raises(VariantEvalError):
            evaluate(expr, VARIANT_DATA)
        return
    assert evaluate(expr, VARIANT_DATA) is case["value"], why


@pytest.mark.parametrize(
    "expr",
    [
        "var.__class__ == 'x'",
        "().__class__.__bases__[0].__subclasses__()",
        "var.name.__class__ == str",
        "__import__('os').system('id') == 0",
        "var.name.format() == 'x'",
        "[x for x in var.tags]",
        "var.name.encode() == b''",
        "lambda: 1",
        "var.a if var.b else var.c",
        "var.name.upper.__self__ == 'x'",
        "var.name.startswith('a', 1)",
        "var.name.startswith(var.edition)",
        "var.edition == 'pro' if True else False",
        "{'a': 1} == var.build",
        "var.count.__add__(1) > 2",
    ],
    ids=lambda expr: expr,
)
def test_adversarial_forms_are_refused(expr: str) -> None:
    """Forms an ``eval``-based reader would have to whitelist its way out of.

    None of these can *execute* here — the interpreter holds a plain mapping and
    never calls anything the grammar did not name — so this suite pins the
    grammar rather than a sandbox. That is the point of interpreting rather than
    evaluating: the whitelist's completeness is a correctness property, and its
    failure mode is a refused condition, not arbitrary code in someone's docs
    build.
    """
    with pytest.raises(VariantConditionError):
        validate(expr)


def test_a_type_mismatch_is_an_evaluation_error_not_a_grammar_error() -> None:
    """A wrongly-typed operand excludes rather than refusing the build.

    ``var.name < 1`` is perfectly well-formed and only the *data* makes it
    fail, so it belongs on the accept-plus-evaluation-error side of the line —
    the same side an unknown key is on, and for the same reason. The exact
    behaviour is ubCode's, not Python's; see
    ``test_variant_grammar_parity.py``.
    """
    validate("var.name < 1")
    with pytest.raises(VariantEvalError, match="number comparison"):
        evaluate("var.name < 1", VARIANT_DATA)


def test_a_string_method_on_a_non_string_is_an_evaluation_error() -> None:
    """``var.count.startswith('1')`` parses; the data is what refuses it."""
    validate("var.count.startswith('1')")
    with pytest.raises(VariantEvalError, match="string predicate"):
        evaluate("var.count.startswith('1')", VARIANT_DATA)


def test_the_boolean_literal_footgun_names_the_real_mistake() -> None:
    """A TOML-spelled ``false`` is a field name; say so, not "write var.false"."""
    with pytest.raises(VariantConditionError, match="Python-spelled"):
        validate("var.debug == false")


def test_a_prefix_less_name_names_the_var_rewrite() -> None:
    with pytest.raises(VariantConditionError, match=r"write `var\.edition`"):
        validate("edition == 'pro'")


def test_no_eval_or_exec_anywhere_in_the_extension() -> None:
    """The security argument, asserted rather than claimed.

    An extension with zero ``eval`` / ``exec`` passes a security review by
    inspection, which matters for a tool aimed at requirements-management users.
    The check is textual on purpose: it also catches a future contributor
    reaching for ``eval`` in a module that has nothing to do with variants.
    """
    package = Path(__file__).parent.parent / "src" / "sphinx_mounts"
    offenders: list[str] = []
    for module in sorted(package.glob("*.py")):
        text = module.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "eval(" in stripped or "exec(" in stripped:
                offenders.append(f"{module.name}:{lineno}: {stripped}")
    assert not offenders, f"eval/exec found in the extension: {offenders}"


def test_variants_module_imports_nothing_from_sphinx_or_this_package() -> None:
    """The extraction discipline, pinned.

    ``variants.py`` and ``dialect.py`` are written to be moved into a shared
    package with ``git mv``. An import of ``sphinx`` or of a sibling module is
    exactly what would make that a rewrite instead, and it is the kind of thing
    that arrives one convenience import at a time.
    """
    package = Path(__file__).parent.parent / "src" / "sphinx_mounts"
    for name in DEPENDENCY_FREE_MODULES:
        text = (package / name).read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            assert "sphinx" not in stripped, f"{name}:{lineno}: {stripped}"
            assert "docutils" not in stripped, f"{name}:{lineno}: {stripped}"
