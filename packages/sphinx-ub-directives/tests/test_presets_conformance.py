"""Directive presets, held to the shared conformance corpus.

``tests/fixtures/directive_presets_conformance.toml`` is the executable half of
``design/directives-contract.md`` §3. This repository is its repository of record and
ubCode vendors it, so every case is a statement both tools are held to. Each case is one
project built with the ``needs`` builder; its needs (type-strict) and its findings (a
multiset of code and attribution) are asserted, and a case with an ``equivalent`` page
is built twice and must give the same products both times. The case COUNT is pinned, so
a trimmed corpus is a red test.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from .corpus import CONF_PY, FIXTURES, build, complete, load, problems
from .corpus import project as _project

#: The presets corpus header's `conf.py`: the shared one, plus autodoc, so a preset of a
#: directive ubCode renders as its generic placeholder (`autoclass`) runs on both sides.
PRESETS_CONF_PY = CONF_PY.replace(
    '"myst_parser", ', '"myst_parser", "sphinx.ext.autodoc", '
)


assert "sphinx.ext.autodoc" in PRESETS_CONF_PY


def project(case: dict[str, Any], page: str) -> list[tuple[Path, str]]:
    return _project(case, page, PRESETS_CONF_PY)


CORPUS = "directive_presets_conformance.toml"

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNT = 111

#: The codes of the presets contract (§8), compared bare.
CODES = frozenset(
    {
        "directive_preset_unknown_base",
        "directive_preset_base_is_preset",
        "directive_preset_name_taken",
        "directive_preset_unknown_option",
        "directive_preset_invalid_value",
        "directive_preset_option_conflict",
        "directive_preset_append_not_list",
        "directive_preset_argument_not_accepted",
        "directive_preset_identity_option",
        "directive_preset_unknown_key",
        "preset_forced_option",
    }
)

CASES = load(CORPUS)


def test_the_corpus_still_has_every_case() -> None:
    assert len(CASES) == EXPECTED_CASE_COUNT, (
        f"{CORPUS} carries {len(CASES)} cases, expected {EXPECTED_CASE_COUNT}. Adding a "
        "case means raising EXPECTED_CASE_COUNT; anything else means cases were lost."
    )


def test_every_case_name_is_unique() -> None:
    names = Counter(case["name"] for case in CASES)
    assert [name for name, count in names.items() if count > 1] == []


def test_every_case_has_a_complete_expectation() -> None:
    """Every case says why and what it builds, the findings (``[]`` for none), and pins
    at least one need, absence or equivalent page."""
    for case in CASES:
        complete(
            case,
            codes=CODES,
            expect_keys=frozenset({"findings", "needs", "nulls", "missing"}),
        )
        expect = case["expect"]
        assert (
            expect.get("needs")
            or expect.get("nulls")
            or expect.get("missing")
            or expect["findings"]
            or case.get("equivalent")
        ), case["name"]


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    header = (FIXTURES / CORPUS).read_text(encoding="utf-8")
    assert f"packages/sphinx-ub-directives/tests/fixtures/{CORPUS}" in header
    assert "THIS copy is CANONICAL" in header


@pytest.mark.parametrize(
    "relative", ["../x.json", "/x.json", "a/../../x.json", "C:/x.json"]
)
def test_a_case_cannot_write_outside_its_directory(relative: str) -> None:
    with pytest.raises(AssertionError, match="outside the case directory"):
        project({"config": "", "files": {relative: "{}"}}, "")


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            case,
            id=case["name"],
            marks=[pytest.mark.skip(reason="ubcode_only")]
            if case.get("ubcode_only")
            else [],
        )
        for case in CASES
    ],
)
def test_case(
    case: dict[str, Any], make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    built = build(
        make_app,
        tmp_path / "source",
        project(case, case["source"]),
        CODES,
        case.get("page", "index"),
    )
    found = problems(built, case["expect"])
    if "equivalent" in case:
        twin = build(
            make_app,
            tmp_path / "equivalent",
            project(case, case["equivalent"]),
            CODES,
            case.get("page", "index"),
        )
        page, needs = built.products()
        twin_page, twin_needs = twin.products()
        if page != twin_page:
            found.append(
                f"the page differs from its equivalent:\n{page}\n---\n{twin_page}"
            )
        if needs != twin_needs:
            found.append(
                f"the needs differ from the equivalent's:\n{needs}\n---\n{twin_needs}"
            )
    assert found == [], case["why"]
