"""An extension declares a field on its own need types alone (#2372).

``add_field(name, description, *, types=[...], ...)`` registers the field as the
extension's declaration -- its schema, ``nullable`` and ``default`` -- localised to the
need types named, exactly as a ``[needs.types.<t>.fields.<f>]`` entry of a field no one
else declares is: absent on every other type, where a value set is
``needs.undeclared_for_type``. A type named that nothing registers is a ``needs.config``
warning, the field declared on the others. A project's ``[needs.fields.<f>]`` of the
same name wins and is global; a project's need type entry naming the field adds that
type to the ones declaring it.

The extension is a stub in each project's ``conf.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.api import add_field
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsApiConfigException
from sphinx_needs_testkit import build_warnings

#: the stub extension: adds ``story`` and the field ``points``, on ``story`` alone
#: unless ``types`` says otherwise, from a handler at sphinx-test-reports' priority
STUB = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True

def _register(app, config):
    from sphinx_needs.api import add_field, add_need_type
    from sphinx_needs.exceptions import NeedsApiConfigWarning
    add_need_type(app, "story", "Story", "ST_")
    try:
        add_field(
            "points",
            "Story points",
            types={types!r},
            schema={{"type": "integer", "minimum": 0}},
            nullable=False,
            default=1,
        )
    except NeedsApiConfigWarning:
        pass  # the project's needs_fields entry of the name, as sphinx-test-reports

def setup(app):
    app.connect("config-inited", _register, priority=500)
"""

#: the project's own types
TYPES = """\
[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.story]
title = "Story"
prefix = "ST_"
"""

INDEX = """\
.. story:: Set
   :id: ST_00001
   :points: 3

.. story:: Unset
   :id: ST_00002

.. req:: Not a story
   :id: R_00001
"""

#: a value of the field on a type that does not declare it
SET_ON_REQ = """\
.. req:: Sets it
   :id: R_00002
   :points: 5
"""


def _project(
    config: str = "", index: str = INDEX, types: list[str] | None = None
) -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), STUB.format(types=types or ["story"])),
            (Path("ubproject.toml"), config),
            (Path("index.rst"), "Case\n====\n\n" + index),
        ],
    }


def _version(app: Any) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]


def _declares(app: Any, need_type: str, name: str = "points") -> bool:
    return SphinxNeedsData(app.env).get_schema().for_type(need_type).declares(name)


@pytest.mark.parametrize(
    "test_app", [_project(TYPES, INDEX + "\n" + SET_ON_REQ)], indirect=True
)
def test_the_field_is_declared_on_the_types_named_alone(test_app: Any) -> None:
    """On ``story`` the field is the extension's: its default fills an unset need,
    and it is not nullable. On ``req`` it is absent: null, and a value set there is
    ignored with ``needs.undeclared_for_type``. The needs.json schema block carries
    the extension's declaration, nullable, as the needs of other types hold null."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:14: WARNING: Field 'points' is not declared on need type "
        "'req' and cannot be set in need 'R_00002'; the value '5' is ignored "
        "[needs.undeclared_for_type]"
    ]
    needs = _version(app)["needs"]
    assert needs["ST_00001"]["points"] == 3
    assert needs["ST_00002"]["points"] == 1
    assert needs["R_00001"]["points"] is None
    assert needs["R_00002"]["points"] is None
    assert (_declares(app, "story"), _declares(app, "req")) == (True, False)
    # the extension's declaration, but nullable: the needs of the other types hold null
    assert _version(app)["needs_schema"]["properties"]["points"] == {
        "type": ["integer", "null"],
        "description": "Story points",
        "field_type": "extra",
        "default": 1,
    }
    schema = SphinxNeedsData(app.env).get_schema()
    assert schema.declaring_types("points") == {"story"}


@pytest.mark.parametrize(
    "test_app", [_project(TYPES, types=["story", "epic"])], indirect=True
)
def test_a_type_no_one_registers_is_reported(test_app: Any) -> None:
    """A need type of ``types`` that nothing registers by the time the schema is
    built is one ``needs.config`` warning; the field is declared on the others."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Field 'points' (from add_field) is declared on need types 'story' "
        "and 'epic' alone, but 'epic' is no need type; the field is declared on the "
        "others [needs.config]"
    ]
    assert (_declares(app, "story"), _declares(app, "req")) == (True, False)
    assert _version(app)["needs"]["ST_00002"]["points"] == 1


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            TYPES + '\n[needs.fields.points]\nschema = { type = "integer" }\n',
            INDEX + "\n" + SET_ON_REQ,
        )
    ],
    indirect=True,
)
def test_a_project_field_of_the_name_wins_and_is_global(test_app: Any) -> None:
    """The project's ``[needs.fields.points]`` is the field, on every need type: the
    extension's registration, and its ``types``, give way to it."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert (_declares(app, "story"), _declares(app, "req")) == (True, True)
    assert _version(app)["needs"]["R_00002"]["points"] == 5


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            TYPES + "\n[needs.types.req.fields.points]\n"
            "\n[needs.types.story.fields.points]\nschema = { maximum = 2 }\n",
            INDEX + "\n" + SET_ON_REQ,
        )
    ],
    indirect=True,
)
def test_a_project_type_entry_naming_the_field_declares_it_there(
    test_app: Any,
) -> None:
    """A project's entry naming the field on a type the extension does not declare it
    on adds that type (an empty entry does), with the extension's declaration; on a
    declaring type the entry narrows it, as any type's entry of a field."""
    app = test_app
    app.build()
    assert (_declares(app, "story"), _declares(app, "req")) == (True, True)
    needs = _version(app)["needs"]
    assert needs["R_00002"]["points"] == 5
    # the extension's default and nullable reach the added type too
    assert needs["R_00001"]["points"] == 1
    # the story's narrowing: 3 is above its maximum
    assert [w.rsplit(" ", 1)[-1] for w in build_warnings(app)] == [
        "[sn_schema_violation.field_fail]"
    ]


@pytest.mark.parametrize("types", ["story", [], ["story", 1]])
def test_types_must_name_need_types(types: Any) -> None:
    """``types`` is a sequence of directive names, at least one: a bare string (a
    sequence of characters) is refused rather than read letter by letter."""
    with pytest.raises(NeedsApiConfigException, match="types"):
        add_field("x", "X", types=types)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            TYPES + '\n[needs.types.req.fields.points]\nschema = { type = "string" }\n',
            INDEX + "\n.. req:: Sets it\n   :id: R_00002\n   :points: abc\n",
        )
    ],
    indirect=True,
)
def test_a_refused_entry_does_not_declare_the_field_on_its_type(
    test_app: Any,
) -> None:
    """An entry naming the field on a type the extension does not declare it on, but
    refused (it changes the field's type), declares nothing: the type stays without
    the field, as for a field a project's types declare alone, so a value there is
    ``needs.undeclared_for_type`` and the need is created -- not refused for a value
    the extension's integer cannot hold. The finding names the declaring type."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['req'].fields['points'] cannot be declared with type "
        "'string' (items None): its type is 'integer' (items None), as need type "
        "'story' declares it; the entry is ignored [needs.type_conflict]",
        "<srcdir>/index.rst:14: WARNING: Field 'points' is not declared on need type "
        "'req' and cannot be set in need 'R_00002'; the value 'abc' is ignored "
        "[needs.undeclared_for_type]",
    ]
    assert (_declares(app, "story"), _declares(app, "req")) == (True, False)
    assert _version(app)["needs"]["R_00002"]["points"] is None
