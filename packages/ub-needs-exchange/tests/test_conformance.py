"""The reader, held to the shared conformance corpus.

``tests/fixtures/needs_json_reading_conformance.toml`` is the executable half of
``design/exchange-contract.md``. This package is its repository of record and ubCode is to
vendor it, so every case here is a statement both tools' readers are to be held to. Two
things are asserted and both matter:

* every case's outcome -- a refusal with its code, or the records read and the findings;
* the number of cases, so that a trimmed corpus is a red test rather than quietly reduced
  coverage.
"""

from __future__ import annotations

import json
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from ub_needs_exchange import ExchangeError, load, parse

CORPUS_PATH = Path(__file__).parent / "fixtures" / "needs_json_reading_conformance.toml"

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNT = 92

#: The keys a case may carry, and those its ``[case.expect]`` may: the header defines
#: each. A key outside them is a case this runner would silently not honour.
CASE_KEYS = {"name", "why", "layer", "reader", "json", "options", "divergent", "expect"}

#: The layers the header defines, and the one this runner implements: a case of the other
#: is skipped, counted, as the header's rule for every runner says.
LAYERS = {"document", "ingest"}
IMPLEMENTED = "document"
EXPECT_KEYS = {"error", "diagnostics", "records", "keys", "absent", "unset"}


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


def test_every_case_is_well_formed() -> None:
    """Only keys the header defines, and a layer it defines; a refusal states nothing
    else; every other case states its findings. A ``document`` case names no reader --
    no reader's policy can change it -- and asks only for a version; a case of a layer
    this runner does not implement is held to the keys alone (it is skipped, not run)."""
    for case in CASES:
        name = case["name"]
        assert set(case) <= CASE_KEYS, name
        assert case["why"], name
        assert case["layer"] in LAYERS, name
        if case["layer"] == IMPLEMENTED:
            assert "reader" not in case, name
            assert set(case.get("options", {})) <= {"version"}, name
        expect = case["expect"]
        assert set(expect) <= EXPECT_KEYS, name
        if "error" in expect:
            assert set(expect) == {"error"}, name
        else:
            assert "diagnostics" in expect, name


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    """ubCode's copy names this path; the header must keep saying this one is canonical."""
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert (
        "packages/ub-needs-exchange/tests/fixtures/needs_json_reading_conformance.toml"
        in header
    )
    assert "THIS copy is CANONICAL" in header


def _as_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _outcome(case: dict[str, Any], text: str | Path) -> None:
    """Read *text* (a file's text, or its path) as *case* says, and hold the result to
    the case's expectation."""
    expect = case["expect"]
    requested = case.get("options", {}).get("version")

    def read() -> Any:
        document = load(text) if isinstance(text, Path) else parse(text)
        return document.select_version(requested)

    if "error" in expect:
        with pytest.raises(ExchangeError) as info:
            read()
        assert info.value.code == expect["error"]
        return

    version = read()
    records = version.records()
    by_key = {record.key: record for record in records}
    found = [*version.diagnostics, *(d for r in records for d in r.diagnostics)]
    assert Counter((d.code, d.path) for d in found) == Counter(
        (d["code"], d["path"]) for d in expect["diagnostics"]
    )
    if "keys" in expect:
        assert [record.key for record in records] == expect["keys"]
    for key, fields in expect.get("records", {}).items():
        assert key in by_key, f"no record {key!r} was read"
        assert set(fields) <= set(by_key[key].fields)
        # as JSON values, so that a boolean is not a number nor an integer a float
        assert _as_json(
            {name: by_key[key].fields[name] for name in fields}
        ) == _as_json(fields)
    for key in expect.get("absent", []):
        assert key not in by_key, f"{key!r} was read as a record"
    for key, names in expect.get("unset", {}).items():
        assert key in by_key, f"no record {key!r} was read"
        assert sorted(set(names) & set(by_key[key].fields)) == []


def _implemented(case: dict[str, Any]) -> None:
    if case["layer"] != IMPLEMENTED:
        pytest.skip(f"layer {case['layer']!r}: this runner implements {IMPLEMENTED!r}")


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_case(case: dict[str, Any]) -> None:
    _implemented(case)
    _outcome(case, case["json"])


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_case_read_from_a_file(case: dict[str, Any], tmp_path: Path) -> None:
    """The same outcome when the text is a file on disk, read by ``load``."""
    _implemented(case)
    path = tmp_path / "needs.json"
    path.write_text(case["json"], encoding="utf-8")
    _outcome(case, path)
