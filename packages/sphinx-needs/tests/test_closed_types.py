"""A need type may be ``closed``: its needs hold only the fields it declares.

On a closed need type, every field the project declares (``needs_fields``,
``needs_extra_options``) and every link type but ``parent_needs`` that the type does
not declare -- by its own entry, or an ancestor's; an empty entry declares -- is
absent: an author's value is refused (``needs.undeclared_for_type``), a need from
outside drops it, a ``needextend`` does not extend it, and the need holds its empty
value. The core fields, and the fields an extension or a service registers, stay as
declared. ``closed`` is inherited, and a type may say otherwise.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args

import pytest

from sphinx_needs.api.need import generate_need
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import WarningSubTypeDescription, WarningSubTypes
from sphinx_needs.needs_schema import (
    FieldSchema,
    FieldsSchema,
    LinkDisplayConfig,
    LinkSchema,
)
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

#: the default need types but ``need``, as a table keyed by directive
BASE_TYPES: dict[str, dict[str, Any]] = {
    "req": {"title": "Requirement", "prefix": "R_"},
    "spec": {"title": "Specification", "prefix": "S_"},
    "impl": {"title": "Implementation", "prefix": "I_"},
    "test": {"title": "Test Case", "prefix": "T_"},
}

#: a field
X = {"nullable": True}
#: a link type
BLOCKS = {"incoming": "is blocked by", "outgoing": "blocks"}


def _types(**declarations: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """``BASE_TYPES``, each named type with its declarations added (a type not in
    ``BASE_TYPES`` is added, with a title and a prefix of its own)."""
    types = {
        name: {**entry, **declarations.get(name, {})}
        for name, entry in BASE_TYPES.items()
    }
    for name, entry in declarations.items():
        if name not in types:
            types[name] = {"title": name, "prefix": "C_", **entry}
    return types


def _conf(
    types: object,
    fields: dict[str, Any] | None = None,
    links: dict[str, Any] | None = None,
    extra: str = "",
) -> str:
    conf = CONF + f"needs_types = {types!r}\n"
    if fields is not None:
        conf += f"needs_fields = {fields!r}\n"
    if links is not None:
        conf += f"needs_links = {links!r}\n"
    return conf + extra


def _project(conf: str, index: str = "") -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Case\n====\n\n" + index),
        ],
    }


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _schema(app: Any) -> FieldsSchema:
    return SphinxNeedsData(app.env).get_schema()


def _field(app: Any, need_type: str | None, name: str) -> Any:
    """The declaration of ``name`` the needs of ``need_type`` read."""
    field = _schema(app).for_type(need_type).get_any_field(name)
    assert field is not None
    return field


def _undeclared(
    line: int | None,
    need_type: str,
    value: object,
    name: str = "x",
    what: str = "Field",
) -> str:
    at = "" if line is None else f"<srcdir>/index.rst:{line}: "
    return (
        f"{at}WARNING: {what} {name!r} is not declared on need type {need_type!r}, "
        f"which is closed, and cannot be set in a need; the value {value!r} is "
        "ignored [needs.undeclared_for_type]"
    )


def test_the_code_is_listed() -> None:
    """The code is in the list the documentation renders for ``suppress_warnings``."""
    assert "undeclared_for_type" in get_args(WarningSubTypes)
    assert WarningSubTypeDescription["undeclared_for_type"] == (
        "A field or link type is set on a need of a closed need type that does not "
        "declare it; the value is ignored"
    )


# -- the projection, on a schema built by hand ----------------------------------------


def _link(name: str) -> LinkSchema:
    return LinkSchema(
        name=name,
        schema={"type": "array", "items": {"type": "string"}},
        display=LinkDisplayConfig(incoming=f"{name} in", outgoing=f"{name} out"),
        directive_option=True,
        allow_extend=True,
        allow_defaults=True,
    )


def _open_field(name: str) -> FieldSchema:
    return FieldSchema(
        name=name,
        schema={"type": "string"},
        nullable=True,
        directive_option=True,
        allow_extend=True,
        allow_defaults=True,
    )


def _hand_built() -> FieldsSchema:
    """``x`` and ``y`` the project's fields, ``e`` an extension's, ``status`` a core
    field; ``links``, ``blocks`` and ``parent_needs`` link types."""
    schema = FieldsSchema()
    schema.add_core_field(_open_field("status"))
    schema.add_extra_field(_open_field("x"), project=True)
    schema.add_extra_field(_open_field("y"), project=True)
    schema.add_extra_field(_open_field("e"))
    for name in ("links", "blocks", "parent_needs"):
        schema.add_link_field(_link(name))
    schema.set_need_types(["req", "spec", "impl"])
    return schema


def test_a_closed_type_is_projected_in_its_view() -> None:
    """A closed type's view holds, for each field and link type of the project it
    does not declare, one absent declaration -- not authorable, not extendable --
    shared with every closed type; what it declares, the core fields, the fields of an
    extension and ``parent_needs`` are the global declarations. No need type declares
    a field anew by being closed."""
    schema = _hand_built()
    schema.close_type("spec", ["y"])
    schema.close_type("impl", [])
    spec, impl, every = (schema.for_type(t) for t in ("spec", "impl", None))
    assert spec is not every
    assert impl is not every
    assert schema.for_type("req") is every
    for name in ("x", "links", "blocks"):
        absent = spec.get_any_field(name)
        assert absent is not None
        assert (absent.directive_option, absent.allow_extend) == (False, False)
        assert impl.get_any_field(name) is absent
        assert every.get_any_field(name) is schema.global_declaration(name)
        assert dict(schema.type_declarations(name)) == {}
    assert impl.get_any_field("y") is not every.get_any_field("y")
    for name in ("y", "e", "status", "parent_needs"):
        assert spec.get_any_field(name) is every.get_any_field(name)
    for name in ("e", "status", "parent_needs"):
        assert impl.get_any_field(name) is every.get_any_field(name)


def test_a_closed_type_declares_what_it_overlays() -> None:
    """A field a closed type declares anew is the type's declaration, not absent."""
    schema = _hand_built()
    narrowed = FieldSchema(
        name="x",
        schema={"type": "string", "minLength": 1},
        nullable=True,
        directive_option=True,
        allow_extend=True,
        allow_defaults=True,
    )
    schema.add_type_overlay("spec", narrowed)
    schema.close_type("spec", [])
    spec = schema.for_type("spec")
    assert spec.get_any_field("x") is narrowed
    y = spec.get_any_field("y")
    assert y is not None
    assert y.directive_option is False


def test_closing_a_type_is_checked() -> None:
    """Only a configured need type is closed, while the schema is built; closing it
    again replaces what it declares."""
    schema = _hand_built()
    with pytest.raises(ValueError) as exc_info:
        schema.close_type("bogus", [])
    assert str(exc_info.value) == (
        "Cannot close need type 'bogus': 'bogus' is not a configured need type."
    )
    schema.close_type("spec", ["x"])
    schema.close_type("spec", ["y"])
    spec = schema.for_type("spec")
    x, y = spec.get_any_field("x"), spec.get_any_field("y")
    assert x is not None
    assert y is not None
    assert (x.directive_option, y.directive_option) == (False, True)
    with pytest.raises(TypeError):
        schema.close_type("impl", [])


# -- closed in the configuration: inherited, overridable ------------------------------

INHERITED_INDEX = """\
.. req:: A
   :id: R_001
   :x: a
   :y: b

.. spec:: B
   :id: S_001
   :x: a
   :y: b

.. impl:: C
   :id: I_001
   :x: a
   :y: b

.. test:: D
   :id: T_001
   :x: a
   :y: b

.. tcase:: E
   :id: C_001
   :x: a
   :y: b
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={"closed": True, "fields": {"x": {}}},
                    impl={"inherits": "spec"},
                    test={"inherits": "spec", "closed": False},
                    tcase={"inherits": "req", "closed": True},
                ),
                {"x": X, "y": X},
            ),
            INHERITED_INDEX,
        )
    ],
    indirect=True,
)
def test_closed_is_inherited_and_overridable(test_app: Any) -> None:
    """A type is closed if its entry says so, else if its parent is: a child of a
    closed type is closed unless it says ``closed = false``, a child of an open type
    open unless it says ``closed = true``. A closed type declares what its ancestors
    declare."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _undeclared(9, "spec", "b", "y"),
        _undeclared(14, "impl", "b", "y"),
        _undeclared(24, "tcase", "a"),
        _undeclared(24, "tcase", "b", "y"),
    ]
    assert {k: (v["x"], v["y"]) for k, v in _needs(app).items()} == {
        "R_001": ("a", "b"),
        "S_001": ("a", None),
        "I_001": ("a", None),
        "T_001": ("a", "b"),
        "C_001": (None, None),
    }
    assert _field(app, "test", "y") is _field(app, None, "y")
    assert _field(app, "impl", "y").directive_option is False


# -- what closed closes, and what it leaves ------------------------------------------

EXEMPT_CONF = """
from sphinx_needs.api import add_field


def setup(app):
    add_field("ext_f", "a field an extension registers", nullable=True)
"""

EXEMPT_INDEX = """\
.. req:: A
   :id: R_001

.. spec:: B
   :id: S_001
   :status: open
   :tags: a
   :ext_f: kept
   :completion: 50
   :x: refused
   :links: R_001
   :blocks: R_001

   .. spec:: C
      :id: S_002
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(spec={"closed": True}),
                {
                    "x": X,
                    "dv": {
                        "schema": {"type": "string"},
                        "nullable": True,
                        "derive_by_type": {"req": {"kind": "copy", "field": "title"}},
                    },
                },
                {"blocks": BLOCKS},
                EXEMPT_CONF,
            ),
            EXEMPT_INDEX,
        )
    ],
    indirect=True,
)
def test_what_closed_closes_and_what_it_leaves(test_app: Any) -> None:
    """A closed type closes the fields and link types the project declares, the
    default ``links`` included; the core fields, the fields an extension or a service
    registers, ``parent_needs`` and the derived fields stay as declared."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _undeclared(7, "spec", "refused"),
        _undeclared(7, "spec", "R_001", "blocks", "Link type"),
        _undeclared(7, "spec", "R_001", "links", "Link type"),
    ]
    needs = _needs(app)
    assert {
        key: needs["S_001"][key]
        for key in ("status", "tags", "ext_f", "completion", "x", "links", "blocks")
    } == {
        "status": "open",
        "tags": ["a"],
        "ext_f": "kept",
        "completion": 50,
        "x": None,
        "links": [],
        "blocks": [],
    }
    assert needs["S_002"]["parent_needs"] == ["S_001"]
    for name in ("status", "tags", "ext_f", "completion", "dv", "parent_needs", "url"):
        # ``url``: an option of the GitHub service
        assert _field(app, "spec", name) is _field(app, None, name), name
    for name in ("x", "links", "blocks"):
        assert _field(app, "spec", name).directive_option is False, name


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={"closed": True, "fields": {"x": {}}, "links": {"links": {}}}
                ),
                {"x": X},
                {"blocks": BLOCKS},
            ),
            ".. req:: A\n   :id: R_001\n\n.. spec:: B\n   :id: S_001\n   :x: kept\n"
            "   :links: R_001\n   :blocks: R_001\n",
        )
    ],
    indirect=True,
)
def test_an_empty_entry_declares(test_app: Any) -> None:
    """An entry that changes nothing declares the field for a closed type."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _undeclared(7, "spec", "R_001", "blocks", "Link type")
    ]
    assert {k: (v["x"], v["links"], v["blocks"]) for k, v in _needs(app).items()} == {
        "R_001": (None, [], []),
        "S_001": ("kept", ["R_001"], []),
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(_types(spec={"closed": True})),
            ".. spec:: A\n   :id: S_001\n\n.. impl:: A\n   :id: I_001\n",
        )
    ],
    indirect=True,
)
def test_a_closed_type_without_project_fields_holds_the_same(test_app: Any) -> None:
    """A need of a closed type that sets nothing holds what a need of an open type
    holds."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = _needs(app)
    differ = {
        key
        for key in needs["S_001"].keys() | needs["I_001"].keys()
        if needs["S_001"].get(key) != needs["I_001"].get(key)
    }
    assert differ == {"id", "type", "type_name", "lineno"}


@pytest.mark.parametrize(
    "test_app",
    [_project(_conf(_types(spec={"closed": True}), {"x": X}))],
    indirect=True,
)
def test_add_need_takes_the_value_and_refuses_it(test_app: Any) -> None:
    """``add_need`` takes a keyword of a field a closed type does not declare -- it is
    a field of the project -- and refuses its value, as a need directive does."""
    app = test_app
    app.build()
    need = generate_need(
        NeedsSphinxConfig(app.config),
        _schema(app),
        "spec",
        "A",
        id="S_001",
        x="given",
    )
    assert need["x"] is None
    assert build_warnings(app) == [_undeclared(None, "spec", "given")]


# -- validation -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(spec={"closed": True}),
                {
                    "s": {
                        "schema": {"type": "string", "minLength": 1},
                        "nullable": False,
                        "default": "A",
                    },
                    "d": {"nullable": True, "default": "dflt"},
                },
            ),
            ".. req:: A\n   :id: R_001\n\n.. spec:: B\n   :id: S_001\n",
        )
    ],
    indirect=True,
)
def test_an_undeclared_field_is_not_validated(test_app: Any) -> None:
    """A field a closed type does not declare holds the empty value of its type, not
    the field's default (``None`` where nullable): it holds no value, and its schema
    is not checked against it."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert {k: (v["s"], v["d"]) for k, v in _needs(app).items()} == {
        "R_001": ("A", "dflt"),
        "S_001": ("", None),
    }


# -- the configuration --------------------------------------------------------------------

#: a ``config-inited`` handler after the normaliser (priority 12), before the need
#: directives are registered, appending an entry to ``needs_types`` as it is, not
#: through ``add_need_type``
APPENDING = """
def _append(app, config):
    config.needs_types.append({entry!r})


def setup(app):
    app.connect("config-inited", _append, priority=13)
"""

EXT = {"directive": "ext", "title": "Extension", "prefix": "E_"}


@pytest.mark.parametrize(
    ("test_app", "warnings", "closed"),
    [
        pytest.param(
            _project(
                _conf(_types(spec={"closed": "yes"}), {"x": X}),
                ".. spec:: A\n   :id: S_001\n   :x: kept\n",
            ),
            [
                "WARNING: needs_types['spec'] has a 'closed' that is not a boolean (got "
                "str); the key is ignored [needs.config]"
            ],
            False,
            id="not-a-boolean",
        ),
        pytest.param(
            _project(
                _conf(_types(), {"x": X}, None, APPENDING.format(entry={**EXT})),
                ".. ext:: A\n   :id: E_001\n   :x: kept\n",
            ),
            [],
            False,
            id="appended-open",
        ),
        pytest.param(
            _project(
                _conf(
                    _types(),
                    {"x": X},
                    None,
                    APPENDING.format(entry={**EXT, "closed": 1}),
                ),
                ".. ext:: A\n   :id: E_001\n   :x: kept\n",
            ),
            [
                "WARNING: needs_types['ext'] has a 'closed' that is not a boolean (got "
                "int); the key is ignored [needs.config]"
            ],
            False,
            id="appended-not-a-boolean",
        ),
        pytest.param(
            _project(
                _conf(
                    _types(),
                    {"x": X},
                    None,
                    APPENDING.format(entry={**EXT, "closed": True}),
                ),
                ".. ext:: A\n   :id: E_001\n   :x: kept\n",
            ),
            [_undeclared(4, "ext", "kept")],
            True,
            id="appended-closed",
        ),
    ],
    indirect=["test_app"],
)
def test_closed_is_a_boolean(test_app: Any, warnings: list[str], closed: bool) -> None:
    """``closed`` is a boolean, in the configuration and in an entry an extension
    appends to it later; anything else is reported and ignored, and the type open."""
    app = test_app
    app.build()
    assert build_warnings(app) == warnings
    assert [need["x"] for need in _needs(app).values()] == [None if closed else "kept"]
