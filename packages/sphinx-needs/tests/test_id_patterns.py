"""The id :ref:`needs_id_regex` and a need type's ``id_regex`` are matched against.

Both patterns accept a need's id when its LOCAL id matches, or the id as a whole
(``needs_namespaced_ids``): ``nc::REQ_1`` is the local id ``REQ_1`` in the namespace
``nc``; a plain id is its own local id. ``sphinx_needs._namespaced_ids.
id_matched_by_patterns`` is the one place both read it from, and these tests pin that
both do: each pattern alone accepts a local id the whole id fails, and refuses one that
neither matches. The default pattern's behaviour on namespaced ids is pinned in
``test_namespaced_ids.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs._namespaced_ids import id_matched_by_patterns
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


@pytest.mark.parametrize("test_app", [_project("^REQ_", "NS::REQ_1")], indirect=True)
def test_both_patterns_match_the_local_id(test_app: Any) -> None:
    """``NS::REQ_1`` is created: neither pattern accepts the whole id, both accept its
    local id ``REQ_1``."""
    test_app.build()
    assert build_warnings(test_app) == []
    assert list(_needs(test_app)) == ["NS::REQ_1"]


@pytest.mark.parametrize(
    ("test_app", "refusal"),
    [
        pytest.param(
            _project("^REQ_", "NS::X_1"),
            "Given ID 'NS::X_1' does not match configured regex '^REQ_', nor does its "
            "local id 'X_1'",
            id="needs_id_regex",
        ),
        pytest.param(
            _project(".*", "NS::X_1"),
            "Given ID 'NS::X_1' does not match the id_regex 'REQ_1' of need type "
            "'req', nor does its local id 'X_1'",
            id="type-id_regex",
        ),
    ],
    indirect=["test_app"],
)
def test_each_pattern_refuses_what_neither_matches(test_app: Any, refusal: str) -> None:
    """``NS::X_1``, whose local id and whole id each pattern refuses, is refused by
    each pattern alone, and the refusal names the local id too."""
    test_app.build()
    warnings = build_warnings(test_app)
    assert len(warnings) == 1
    assert refusal in warnings[0]
    assert _needs(test_app) == {}


@pytest.mark.parametrize("test_app", [_project("^REQ_", "REQ_1")], indirect=True)
def test_the_local_id_is_the_whole_id(test_app: Any) -> None:
    """A plain id is its own local id: nothing changes."""
    assert id_matched_by_patterns("^REQ_", "REQ_1", "REQ_1")
    assert not id_matched_by_patterns("^REQ_", "X_1", "X_1")
    assert id_matched_by_patterns("^REQ_", "REQ_1::A", "A")
    assert not id_matched_by_patterns("^REQ_1$", "NS::REQ_1x", "REQ_1x", full=True)
    test_app.build()
    assert build_warnings(test_app) == []
    assert list(_needs(test_app)) == ["REQ_1"]
