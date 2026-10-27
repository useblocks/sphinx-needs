# @Test suite for the code entity on the needs created from code, TEST_CODE_ENTITY_1, test, [IMPL_ENTITY_1]
"""``set_code_entity``: the code entity a marker is attached to, on the need it creates.

Every case builds a copy of ``doc_test/code_entity``: ``src/shapes.py`` holds a one-line
need above a function (``IMPL_FN``), a multi-line need above a decorated function
(``IMPL_ML``), a one-line need above a method (``IMPL_METHOD``), a one-line need
trailing a module-level statement, attached to no entity (``IMPL_NONE``), and a
reference to ``REQ_001`` (which ``index`` defines) by an ``@need-ids`` marker.
"""

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_codelinks.sphinx_extension.code_entity import (
    CODE_ENTITY_FIELDS,
    code_entity_values,
)
from sphinx_needs_testkit import build_warnings

from .test_need_id_refs import _SHOWS_WARNING_TYPES, _build, _git, _json

FIXTURE = Path(__file__).parent / "doc_test" / "code_entity"

_MakeApp = Callable[..., SphinxTestApp]


def _project(root: Path, *, toml_replace: tuple[str, str] | None = None) -> None:
    """Copy the fixture into ``root``, change it, and make it a git repository."""
    shutil.copytree(FIXTURE, root, dirs_exist_ok=True)
    if toml_replace is not None:
        toml = root / "docs" / "ubproject.toml"
        text = toml.read_text(encoding="utf-8")
        assert toml_replace[0] in text
        toml.write_text(text.replace(*toml_replace), encoding="utf-8")
    _git(root, "init", "--quiet")
    _git(root, "remote", "add", "origin", "https://github.com/example/demo.git")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "init")


def _entities(app: SphinxTestApp) -> dict[str, dict[str, Any]]:
    """Each need's code entity fields that are set (not ``None``)."""
    needs = _json(app)["needs"]
    return {
        need_id: {
            name: need[name]
            for name in CODE_ENTITY_FIELDS
            if need.get(name) is not None
        }
        for need_id, need in needs.items()
    }


def test_created_needs_carry_the_attached_entity(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """One-line and multi-line needs carry the entity their marker is attached to; a
    decorated function's lines are its own (``def`` to its end), a need attached to no
    entity and a need a reference names carry none of the fields."""
    _project(tmp_path)
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == []
    assert _entities(app) == {
        "IMPL_FN": {
            "code_entity": "handler",
            "code_entity_kind": "function",
            "code_entity_lines": [2, 3],
            "code_entity_mechanism": "leading",
        },
        "IMPL_ML": {
            "code_entity": "decorated",
            "code_entity_kind": "function",
            "code_entity_lines": [10, 12],
            "code_entity_mechanism": "leading",
        },
        "IMPL_METHOD": {
            "code_entity": "Shape.area",
            "code_entity_kind": "method",
            "code_entity_lines": [17, 18],
            "code_entity_mechanism": "leading",
        },
        "IMPL_NONE": {},
        "REQ_001": {},
    }


def test_the_fields_are_registered_typed(tmp_path: Path, make_app: _MakeApp) -> None:
    """The four fields are declared with their types -- two strings, an array of
    integers, a string -- each nullable, so a need without an entity has none."""
    _project(tmp_path)
    app = _build(tmp_path, make_app)

    fields = _json(app)["needs_schema"]["properties"]
    assert fields["code_entity"]["type"] == ["string", "null"]
    assert fields["code_entity_kind"]["type"] == ["string", "null"]
    assert fields["code_entity_lines"]["type"] == ["array", "null"]
    assert fields["code_entity_lines"]["items"] == {"type": "integer"}
    assert fields["code_entity_mechanism"]["type"] == ["string", "null"]


def test_off_by_default(tmp_path: Path, make_app: _MakeApp) -> None:
    """Without ``set_code_entity`` no need carries, nor declares, the fields."""
    _project(tmp_path, toml_replace=("set_code_entity = true\n", ""))
    app = _build(tmp_path, make_app)

    data = _json(app)
    assert all(
        name not in need
        for need in data["needs"].values()
        for name in CODE_ENTITY_FIELDS
    )
    assert not set(CODE_ENTITY_FIELDS) & set(data["needs_schema"]["properties"])


def test_a_user_declared_field_of_the_same_name_warns(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """codelinks registers the fields itself: declaring one in ``needs_fields`` as
    well is reported, as for the ``@need-ids`` field."""
    _project(tmp_path)
    conf = tmp_path / "docs" / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8")
        + 'needs_fields = {"code_entity_kind": {"description": "mine"}}\n',
        encoding="utf-8",
    )
    app = _build(tmp_path, make_app)

    message = (
        "codelinks registers 'code_entity_kind' for set_code_entity; remove the "
        "needs_fields declaration of it, or turn set_code_entity off"
    )
    suffix = " [codelinks.config]" if _SHOWS_WARNING_TYPES else ""
    assert f"WARNING: {message}{suffix}" in build_warnings(app)


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        pytest.param(None, {}, id="no-entity"),
        pytest.param(
            {
                "kind": "function_definition",
                "start": 2,
                "end": 3,
                "entity_kind": "function",
                "qualified_name": "f",
                "mechanism": "trailing",
            },
            {
                "code_entity": "f",
                "code_entity_kind": "function",
                "code_entity_lines": [2, 3],
                "code_entity_mechanism": "trailing",
            },
            id="named",
        ),
        pytest.param(
            {
                "kind": "variable_declaration",
                "start": 1,
                "end": 1,
                "entity_kind": None,
                "qualified_name": None,
                "mechanism": "leading",
            },
            {"code_entity_lines": [1, 1], "code_entity_mechanism": "leading"},
            id="unnamed",
        ),
    ],
)
def test_code_entity_values(scope: Any, expected: dict[str, Any]) -> None:
    """The projection of an analysis ``scope`` onto the fields: an unnamed entity
    still has its lines and mechanism, and no entity gives no field."""
    assert code_entity_values(scope) == expected
