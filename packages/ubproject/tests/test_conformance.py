"""The reader, held to the shared conformance corpus.

``tests/fixtures/ubproject_reading_conformance.toml`` is the executable half of
``design/reading-contract.md``. This package is its repository of record and ubCode
vendors it, so every case here is a statement both readers are held to. Two things are
asserted and both matter:

* every case's outcome -- the merged map, the anchored data file and the findings, or a
  refusal;
* the number of cases, so that a trimmed corpus is a red test rather than quietly reduced
  coverage.
"""

from __future__ import annotations

import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from ubproject import UbprojectError, load_toml, read_variants

CORPUS_PATH = Path(__file__).parent / "fixtures" / "ubproject_reading_conformance.toml"

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNT = 55

#: The placeholder a case's ``toml`` uses for the absolute path of its own directory.
CASE_DIR = "{case_dir}"


def _corpus() -> list[dict[str, Any]]:
    with CORPUS_PATH.open("rb") as handle:
        return tomllib.load(handle)["case"]


CASES = _corpus()


def test_the_corpus_still_has_every_case() -> None:
    assert len(CASES) == EXPECTED_CASE_COUNT, (
        f"{CORPUS_PATH.name} carries {len(CASES)} cases, expected "
        f"{EXPECTED_CASE_COUNT}. Adding a case means raising EXPECTED_CASE_COUNT; "
        "anything else means cases were lost."
    )


def test_every_case_name_is_unique() -> None:
    names = Counter(case["name"] for case in CASES)
    assert [name for name, count in names.items() if count > 1] == []


def test_every_case_has_a_complete_expectation() -> None:
    """A refusal states nothing else; every other case states the map and the findings."""
    for case in CASES:
        expect = case["expect"]
        assert case["why"], case["name"]
        if expect.get("error", False):
            assert set(expect) == {"error"}, case["name"]
        else:
            assert {"variant_data", "diagnostics"} <= set(expect), case["name"]
            assert set(expect) <= {
                "variant_data",
                "variant_data_file",
                "diagnostics",
            }, case["name"]


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    """ubCode's copy names this path; the header must keep saying this one is canonical."""
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert (
        "packages/ubproject/tests/fixtures/ubproject_reading_conformance.toml" in header
    )
    assert "THIS copy is CANONICAL" in header


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_case(case: dict[str, Any], tmp_path: Path) -> None:
    case_dir = tmp_path
    for relative, text in case.get("files", {}).items():
        path = case_dir.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    toml_path = case_dir.joinpath(*case.get("toml_path", "ubproject.toml").split("/"))
    toml_path.parent.mkdir(parents=True, exist_ok=True)
    toml_path.write_text(
        case["toml"].replace(CASE_DIR, case_dir.as_posix()), encoding="utf-8"
    )
    expect = case["expect"]
    needs_table = case.get("needs_table", "needs")

    if expect.get("error", False):
        with pytest.raises(UbprojectError):
            read_variants(load_toml(toml_path), toml_path, needs_table=needs_table)
        return

    result = read_variants(load_toml(toml_path), toml_path, needs_table=needs_table)
    assert result.data == expect["variant_data"]
    if "variant_data_file" in expect:
        expected_file = case_dir.joinpath(*expect["variant_data_file"].split("/"))
        assert result.data_file == expected_file
    else:
        assert result.data_file is None
    assert Counter((d.code, d.path) for d in result.diagnostics) == Counter(
        (d["code"], d["path"]) for d in expect["diagnostics"]
    )
