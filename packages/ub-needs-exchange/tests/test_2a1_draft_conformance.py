"""The reader of the draft format "2a1", held to its own conformance corpus.

``tests/fixtures/needs_json_2a1_draft_conformance.toml`` is the executable half of
``design/v2a1-draft.md``. It is NOT the shared reading corpus, which ubCode vendors and
where "2a1" stays refused (``test_conformance.py`` runs that one): the draft is
experimental, and its corpus is this package's own until the shape settles. Two things
are asserted, as for the shared corpus:

* every case's outcome -- a refusal with its code, or the version, the records, their
  hops and the findings;
* the number of cases, so that a trimmed corpus is a red test rather than quietly reduced
  coverage.

The helpers are this module's own, not imported from ``test_conformance.py``: the two
corpora's keys differ (``drafts``, ``name``, ``source``), and each runner states the
header it implements.
"""

from __future__ import annotations

import json
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from ub_needs_exchange import ExchangeError, load, parse

CORPUS_PATH = (
    Path(__file__).parent / "fixtures" / "needs_json_2a1_draft_conformance.toml"
)

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message.
EXPECTED_CASE_COUNT = 75

#: The keys a case may carry, and those its ``[case.options]`` and ``[case.expect]``
#: may: the header defines each. A key outside them is a case this runner would
#: silently not honour.
CASE_KEYS = {"name", "why", "layer", "json", "options", "expect"}
OPTION_KEYS = {"version", "drafts"}
EXPECT_KEYS = {
    "error",
    "diagnostics",
    "name",
    "records",
    "source",
    "keys",
    "absent",
    "unset",
    "nulls",
}

#: The drafts a case is read with when its ``options`` name none.
DEFAULT_DRAFTS = ("2a1",)


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
    """Only keys the header defines, and its one layer; a refusal states nothing else;
    every other case states its findings."""
    for case in CASES:
        name = case["name"]
        assert set(case) <= CASE_KEYS, name
        assert case["why"], name
        assert case["layer"] == "document", name
        assert set(case.get("options", {})) <= OPTION_KEYS, name
        expect = case["expect"]
        assert set(expect) <= EXPECT_KEYS, name
        # an empty list of names would pass whatever the record holds
        for key in ("unset", "nulls"):
            assert all(expect.get(key, {}).values()), f"{name}: an empty {key} list"
        if "error" in expect:
            assert set(expect) == {"error"}, name
        else:
            assert "diagnostics" in expect, name


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert (
        "packages/ub-needs-exchange/tests/fixtures/needs_json_2a1_draft_conformance.toml"
        in header
    )
    assert "EXPERIMENTAL" in header


def test_the_shared_corpus_keeps_2a1_refused() -> None:
    """The positive control of the opt-in: the shared corpus still pins a "2a1" file as
    refused, so the draft is read here only because this runner asks for it."""
    shared = Path(__file__).parent / "fixtures" / "needs_json_reading_conformance.toml"
    with shared.open("rb") as handle:
        cases = {case["name"]: case for case in tomllib.load(handle)["case"]}
    for name in (
        "format-version-a-pre-release-is-refused",
        "format-version-is-checked-whatever-version-is-asked-for",
    ):
        assert cases[name]["expect"] == {"error": "format_version_unsupported"}, name


def _as_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _outcome(case: dict[str, Any], text: str | Path) -> None:
    """Read *text* (a file's text, or its path) as *case* says, and hold the result to
    the case's expectation."""
    expect = case["expect"]
    options = case.get("options", {})
    requested = options.get("version")
    drafts = options.get("drafts", DEFAULT_DRAFTS)

    def read() -> Any:
        document = load(text) if isinstance(text, Path) else parse(text)
        return document.select_version(requested, drafts=drafts)

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
    if "name" in expect:
        assert version.name == expect["name"]
    if "keys" in expect:
        assert [record.key for record in records] == expect["keys"]
    for key, fields in expect.get("records", {}).items():
        assert key in by_key, f"no record {key!r} was read"
        assert set(fields) <= set(by_key[key].fields)
        # as JSON values, so that a boolean is not a number nor an integer a float
        assert _as_json(
            {name: by_key[key].fields[name] for name in fields}
        ) == _as_json(fields)
    for key, hops in expect.get("source", {}).items():
        assert key in by_key, f"no record {key!r} was read"
        assert _as_json(list(by_key[key].source)) == _as_json(hops)
    for key in expect.get("absent", []):
        assert key not in by_key, f"{key!r} was read as a record"
    for key, names in expect.get("unset", {}).items():
        assert key in by_key, f"no record {key!r} was read"
        assert sorted(set(names) & set(by_key[key].fields)) == []
    for key, names in expect.get("nulls", {}).items():
        assert key in by_key, f"no record {key!r} was read"
        fields = by_key[key].fields
        assert {
            name: name in fields and fields[name] is None for name in names
        } == dict.fromkeys(names, True)


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_case(case: dict[str, Any]) -> None:
    _outcome(case, case["json"])


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_case_read_from_a_file(case: dict[str, Any], tmp_path: Path) -> None:
    """The same outcome when the text is a file on disk, read by ``load``."""
    path = tmp_path / "needs.json"
    path.write_text(case["json"], encoding="utf-8")
    _outcome(case, path)
