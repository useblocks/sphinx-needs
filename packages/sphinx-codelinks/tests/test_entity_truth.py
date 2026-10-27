"""Which code entity each marker is attached to, against compiler ground truth.

A case of ``tests/data/extraction/*.yaml`` may carry a ``truth`` list: for each marker
id, the entity a compiler (or, for a rule case, the attachment rule) says the marker
belongs to -- its kind, its name within the file, its first line and, for a rule case,
the mechanism. The case is extracted exactly as ``test_extraction_fixtures.py`` does,
and every marker's ``scope`` is compared with its entry. ``entities.yaml`` documents
the entries and where the truth comes from.

``KNOWN_WRONG_TODAY`` lists the markers the analysis attaches wrongly today. Each one
is asserted to STILL be wrong, so the list cannot go stale: a fix that rights one fails
here until the fix also delists it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from .test_extraction_fixtures import FIXTURE_DIR, _extract

KNOWN_WRONG_TODAY: frozenset[str] = frozenset()
"""Marker ids whose ``scope`` differs from their truth today."""


def _truth_cases() -> list[Any]:
    cases = []
    for path in sorted(FIXTURE_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, case in data.items():
            if "truth" in case:
                cases.append(pytest.param(case, id=f"{path.stem}-{name}"))
    return cases


def _marker_id(item: dict[str, Any]) -> str:
    if item["type"] == "need-id-refs":
        return str(item["need_ids"][0])
    return str(item["need"]["id"])


def _scope(item: dict[str, Any]) -> dict[str, Any] | None:
    if item["type"] == "multiline-need":
        return item["source"]["scope"]
    return item["scope"]


def _difference(scope: dict[str, Any] | None, entry: dict[str, Any]) -> str | None:
    """How ``scope`` differs from the truth ``entry``, or ``None`` if it matches."""
    if entry["entity_kind"] is None:
        return None if scope is None else f"expected no entity, got {scope}"
    if scope is None:
        return "expected an entity, got none"
    expected = {
        key: entry[key]
        for key in ("entity_kind", "qualified_name", "start", "mechanism")
        if key in entry
    }
    got = {key: scope[key] for key in expected}
    return None if got == expected else f"expected {expected}, got {got}"


@pytest.mark.parametrize("case", _truth_cases())
def test_entity_truth(case: dict[str, Any], tmp_path: Path) -> None:
    """Every marker of the case is attached to the entity its truth names."""
    content, _ = _extract(case, tmp_path, case["source"])
    scopes = {_marker_id(item): _scope(item) for item in content}
    truth = {entry["id"]: entry for entry in case["truth"]}
    assert sorted(scopes) == sorted(truth), "every marker has exactly one truth entry"

    wrong = {}
    right_but_listed = []
    for marker_id, entry in truth.items():
        difference = _difference(scopes[marker_id], entry)
        if marker_id in KNOWN_WRONG_TODAY:
            if difference is None:
                right_but_listed.append(marker_id)
        elif difference is not None:
            wrong[marker_id] = difference
    assert not wrong, "attached to the wrong entity:\n" + "\n".join(
        f"  {marker_id}: {difference}" for marker_id, difference in wrong.items()
    )
    assert not right_but_listed, (
        f"now attached right, remove from KNOWN_WRONG_TODAY: {right_but_listed}"
    )


def test_known_wrong_today_names_real_markers() -> None:
    """Every listed id is a marker some case has a truth entry for."""
    ids = {
        entry["id"] for param in _truth_cases() for entry in param.values[0]["truth"]
    }
    assert KNOWN_WRONG_TODAY <= ids, sorted(KNOWN_WRONG_TODAY - ids)
