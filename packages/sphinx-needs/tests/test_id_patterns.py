"""The id :ref:`needs_id_regex` and a need type's ``id_regex`` are matched against.

Both patterns match the need's local id, the id as it is written in the need or
generated, before any namespace; while ids carry no namespace, that is the whole id.
``sphinx_needs.api.need._id_matched_by_patterns`` is the one place both read it from,
and these tests pin that both do: each replaces it, so that the local id differs from
the whole one, and checks which of the two each pattern was matched against.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.api import need as need_api
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = {global_!r}
needs_types = [
    {{"directive": "req", "title": "Requirement", "prefix": "R_", "id_regex": "REQ_1"}},
]
"""


def _project(global_: str, need_id: str) -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), CONF.format(global_=global_)),
            (Path("index.rst"), f"Case\n====\n\n.. req:: A\n   :id: {need_id}\n"),
        ],
    }


def _needs(app: Any) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


@pytest.mark.parametrize("test_app", [_project("^REQ_", "NS_REQ_1")], indirect=True)
def test_both_patterns_match_the_local_id(
    test_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a local id that is the whole id without a leading ``NS_``, ``NS_REQ_1``
    is created: neither pattern accepts the whole id, both accept the local one."""
    monkeypatch.setattr(
        need_api, "_id_matched_by_patterns", lambda i: i.removeprefix("NS_")
    )
    test_app.build()
    assert build_warnings(test_app) == []
    assert list(_needs(test_app)) == ["NS_REQ_1"]


@pytest.mark.parametrize(
    ("test_app", "refusal"),
    [
        pytest.param(
            _project("^REQ_", "REQ_1"),
            "Given ID 'REQ_1' does not match configured regex '^REQ_'",
            id="needs_id_regex",
        ),
        pytest.param(
            _project(".*", "REQ_1"),
            "Given ID 'REQ_1' does not match the id_regex 'REQ_1' of need type 'req'",
            id="type-id_regex",
        ),
    ],
    indirect=["test_app"],
)
def test_each_pattern_matches_the_local_id(
    test_app: Any, refusal: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a local id that neither pattern accepts, ``REQ_1``, which both accept,
    is refused by each pattern alone: each is matched against the local id, not the
    whole one."""
    monkeypatch.setattr(need_api, "_id_matched_by_patterns", lambda _: "local")
    test_app.build()
    warnings = build_warnings(test_app)
    assert len(warnings) == 1
    assert refusal in warnings[0]
    assert _needs(test_app) == {}


@pytest.mark.parametrize("test_app", [_project("^REQ_", "REQ_1")], indirect=True)
def test_the_local_id_is_the_whole_id(test_app: Any) -> None:
    """While ids carry no namespace, the local id is the whole id: nothing changes."""
    assert need_api._id_matched_by_patterns("REQ_1") == "REQ_1"
    test_app.build()
    assert build_warnings(test_app) == []
    assert list(_needs(test_app)) == ["REQ_1"]
