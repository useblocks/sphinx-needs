"""Template directives, held to the shared conformance corpus.

``tests/fixtures/template_directives_conformance.toml`` is the executable half of
``design/directives-contract.md`` §4-§7. This repository is its repository of record and
ubCode vendors it. Each case is one project built with the ``needs`` builder; its
expansions (exactly, in document order, read from the package's one render seam), its
needs (type-strict) and its findings (a multiset of code and attribution) are asserted,
and a case with an ``equivalent`` page is built twice and must give the same products
both times. The case COUNT is pinned, so a trimmed corpus is a red test.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_ub_directives import _templates

from .corpus import FIXTURES, build, complete, load, problems, project

CORPUS = "template_directives_conformance.toml"

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNT = 213

#: The codes of the template contract (§8), compared bare.
CODES = frozenset(
    {
        "directive_template_invalid",
        "template_context_reserved",
        "template_switched_off",
        "template_signature",
        "template_option_invalid",
        "template_context_unknown",
        "template_context_invalid",
        "template_context_unavailable",
        "template_missing",
        "template_outside_root",
        "template_render_error",
        "template_output_limit",
        "template_disabled",
        "template_nested_expansion",
        "template_output_reads_file",
        "template_heading",
        "template_markup_construct",
        "directive_template_unknown_key",
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
    for case in CASES:
        complete(
            case,
            codes=CODES,
            expect_keys=frozenset(
                {"expansions", "findings", "needs", "nulls", "missing"}
            ),
        )


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    header = (FIXTURES / CORPUS).read_text(encoding="utf-8")
    assert f"packages/sphinx-ub-directives/tests/fixtures/{CORPUS}" in header
    assert "THIS copy is CANONICAL" in header


def header_minijinja() -> str:
    """The minijinja version the corpus header records."""
    header = (FIXTURES / CORPUS).read_text(encoding="utf-8")
    match = re.search(r"^# minijinja:\s+(\d+\.\d+\.\d+)", header, re.MULTILINE)
    assert match, "the corpus header records no minijinja version"
    return match[1]


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
    case: dict[str, Any],
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expansions: list[str] = []
    monkeypatch.setattr(_templates, "observe", expansions.append)
    built = build(
        make_app,
        tmp_path / "source",
        project(case, case["source"]),
        CODES,
        case.get("page", "index"),
    )
    expect = case["expect"]
    found = problems(built, expect)
    if "expansions" in expect and expansions != expect["expansions"]:
        found.append(f"expansions {expansions!r}, expected {expect['expansions']!r}")
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
