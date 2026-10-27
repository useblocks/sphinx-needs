"""A field may be declared on the need types that have it alone: one name, one shape.

A ``fields`` entry of a need type naming no field the project, an extension or a
service declares -- no ``needs_fields`` entry, no core field, no link type -- declares
a field of its own: the field of the types that declare it (by their own entry, or an
ancestor's; an empty entry declares), absent on every other type. Every type that
declares it agrees on its shape -- its type, its items' type, and whether it is
derived -- which the first declaration of a type without an ancestor declaring it (in
the order a parent comes before its children) that gives a ``schema`` ``type`` sets;
each type is free in the rest. A ``derive`` in a type's entry is a ``derive_by_type``
entry of the field for that type, and reaches the type's children.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, get_args

import pytest

from sphinx_needs.api.need import generate_need
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.derive import DeriveRule
from sphinx_needs.exceptions import NeedsConfigException
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


def _version(app: Any) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    return _version(app)["needs"]


def _properties(app: Any) -> dict[str, Any]:
    return _version(app)["needs_schema"]["properties"]


def _schema(app: Any) -> FieldsSchema:
    return SphinxNeedsData(app.env).get_schema()


def _field(app: Any, need_type: str | None, name: str) -> Any:
    """The declaration of ``name`` the needs of ``need_type`` read."""
    field = _schema(app).for_type(need_type).get_any_field(name)
    assert field is not None
    return field


def _undeclared(
    line: int | None,
    need: str,
    need_type: str,
    value: object,
    name: str = "x",
    what: str = "Field",
) -> str:
    at = "" if line is None else f"<srcdir>/index.rst:{line}: "
    return (
        f"{at}WARNING: {what} {name!r} is not declared on need type {need_type!r} "
        f"and cannot be set in need {need!r}; the value {value!r} is ignored "
        "[needs.undeclared_for_type]"
    )


def _conflict(text: str) -> str:
    return f"WARNING: {text}; the entry is ignored [needs.type_conflict]"


def _shape(
    need_type: str, name: str, own: str, agreed: str, by: str, items: str = "None"
) -> str:
    """The finding of a declaration of another type than the one agreed."""
    return _conflict(
        f"needs_types[{need_type!r}].fields[{name!r}] cannot be declared with type "
        f"{own!r} (items {items}): its type is {agreed!r} (items {items}) on every "
        f"need type, as need type {by!r} declares it"
    )


def _untyped(need_type: str, name: str) -> str:
    """The finding of a declaration of a field no need type gives a type."""
    return _conflict(
        f"needs_types[{need_type!r}].fields[{name!r}] declares {name!r}, which no "
        "needs_fields entry declares, and no need type without an ancestor declaring "
        "it gives it a 'schema' 'type'"
    )


def test_the_code_is_listed() -> None:
    """The code is in the list the documentation renders for ``suppress_warnings``."""
    assert "undeclared_for_type" in get_args(WarningSubTypes)
    assert WarningSubTypeDescription["undeclared_for_type"] == (
        "A field or link type is set on a need of a need type that does not declare "
        "it; the value is ignored"
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
    """``x`` and ``y`` the project's fields, ``status`` a core field; ``links`` and
    ``parent_needs`` link types."""
    schema = FieldsSchema()
    schema.add_core_field(_open_field("status"))
    schema.add_extra_field(_open_field("x"), project=True)
    schema.add_extra_field(_open_field("y"), project=True)
    for name in ("links", "parent_needs"):
        schema.add_link_field(_link(name))
    schema.set_need_types(["req", "spec", "impl"])
    return schema


def test_a_field_of_some_need_types_is_projected_per_field() -> None:
    """A field of some need types alone is absent on every other type: one absent
    declaration -- not authorable, not extendable -- shared by every such type. Every
    other field of those types, the field on a type that declares it, and the global
    view, are the global declarations; a type that lacks no such field reads the
    global view itself."""
    schema = _hand_built()
    schema._localise("x", ["req"])
    req, spec, impl, every = (schema.for_type(t) for t in ("req", "spec", "impl", None))
    assert req is every
    assert spec is not every
    assert impl is not every
    absent = spec.get_any_field("x")
    assert absent is not None
    assert (absent.directive_option, absent.allow_extend) == (False, False)
    assert impl.get_any_field("x") is absent
    assert every.get_any_field("x") is schema.global_declaration("x")
    assert dict(schema.type_declarations("x")) == {}
    for name in ("y", "status", "links", "parent_needs"):
        assert spec.get_any_field(name) is every.get_any_field(name), name
    # a schema without such a field: every type reads the global view
    plain = _hand_built()
    assert plain.for_type("spec") is plain.for_type(None)


def test_localising_a_field_is_checked() -> None:
    """Only a field the schema has is localised, while the schema is built."""
    schema = _hand_built()
    with pytest.raises(ValueError) as exc_info:
        schema._localise("nosuch", ["req"])
    assert str(exc_info.value) == (
        "Cannot declare field 'nosuch' on need types alone: there is no field of "
        "that name."
    )
    schema.freeze()
    with pytest.raises(TypeError):
        schema._localise("x", ["req"])


# -- what a field declared on need types alone is, on every need --------------------

LOCAL_FIELDS = {
    "shared": {"schema": {"type": "string"}, "nullable": True},
    "fp": {"schema": {"type": "string"}, "derive": {"kind": "fingerprint"}},
    "fpx": {
        "schema": {"type": "string"},
        "derive": {"kind": "fingerprint", "exclude": ["x"]},
    },
}

LOCAL_TYPES = _types(
    req={
        "fields": {
            "x": {
                "schema": {"type": "integer", "minimum": 0},
                "nullable": False,
                "default": 1,
            }
        }
    },
    spec={
        "fields": {
            "y": {"schema": {"type": "string", "enum": ["a", "b"]}},
            "shared": {"schema": {"enum": ["s1", "s2"]}},
        }
    },
    impl={"inherits": "req"},
)

LOCAL_INDEX = """\
.. req:: A
   :id: R_001
   :x: 5

.. req:: B
   :id: R_002

.. spec:: C
   :id: S_001
   :x: 4
   :y: a
   :shared: s1

.. impl:: D
   :id: I_001
   :x: 7
   :y: b

.. test:: E
   :id: T_001

.. needextend:: type == 'spec' or type == 'test'
   :x: 9

.. needextend:: R_001
   :x: 8
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(_conf(LOCAL_TYPES, LOCAL_FIELDS), LOCAL_INDEX)],
    indirect=True,
)
def test_a_field_declared_on_need_types_alone(test_app: Any) -> None:
    """A field no ``needs_fields`` entry declares is the field of the types that
    declare it, and their children: a value set for it on a need of another type is
    ignored, and reported; a needextend does not extend it there, one warning for each
    type; such a need holds ``None``, its fingerprint as without the field, while a
    declaring need's value enters it (its type's default too). The needs.json carries
    it on every need, and the field's schema, nullable, with no default."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _undeclared(11, "S_001", "spec", "4"),
        _undeclared(17, "I_001", "impl", "b", "y"),
        "<srcdir>/index.rst:25: WARNING: Option 'x' does not support extend "
        "operations on need type 'spec'; it does not extend 1 need (S_001). "
        "[needs.needextend]",
        "<srcdir>/index.rst:25: WARNING: Option 'x' does not support extend "
        "operations on need type 'test'; it does not extend 1 need (T_001). "
        "[needs.needextend]",
    ]
    needs = _needs(app)
    assert {k: (v["x"], v["y"], v["shared"]) for k, v in needs.items()} == {
        "R_001": (8, None, None),
        "R_002": (1, None, None),
        "S_001": (None, "a", "s1"),
        "I_001": (7, None, None),
        "T_001": (None, None, None),
    }
    assert {k: v["fp"] == v["fpx"] for k, v in needs.items()} == {
        "R_001": False,
        "R_002": False,
        "S_001": True,
        "I_001": False,
        "T_001": True,
    }
    properties = _properties(app)
    assert properties["x"] == {
        "default": None,
        "description": "Declared by need types 'req'",
        "field_type": "extra",
        "type": ["integer", "null"],
    }
    assert properties["y"] == {
        "default": None,
        "description": "Declared by need types 'spec'",
        "field_type": "extra",
        "type": ["string", "null"],
    }
    schema = _schema(app)
    glob = schema.global_declaration("x")
    assert glob is not None
    assert glob.kind == "field"
    assert (glob.schema, glob.nullable, glob.default) == (
        {"type": "integer"},
        True,
        None,
    )
    assert (glob.directive_option, glob.allow_extend, glob.parse_variants) == (
        True,
        True,
        False,
    )
    assert schema.is_project_field("x")
    assert sorted(dict(schema.type_declarations("x"))) == ["impl", "req"]
    absent = _field(app, "spec", "x")
    assert (absent.directive_option, absent.allow_extend) == (False, False)
    assert _field(app, "test", "x") is absent
    assert _field(app, None, "x") is glob
    assert _field(app, "impl", "x") is _field(app, "req", "x")
    assert schema.for_type("test") is not schema.for_type(None)
    # every other field of a type that does not declare it is as declared for all
    for name in ("shared", "fp", "status", "tags", "links", "parent_needs"):
        assert _field(app, "test", name) is _field(app, None, name), name


@pytest.mark.parametrize(
    "test_app",
    [_project(_conf(LOCAL_TYPES, LOCAL_FIELDS))],
    indirect=True,
)
def test_add_need_takes_the_value_and_refuses_it(test_app: Any) -> None:
    """``add_need`` takes a keyword of a field another type declares -- it is a field
    of the project -- and refuses its value, as a need directive does."""
    app = test_app
    app.build()
    need = generate_need(
        NeedsSphinxConfig(app.config),
        _schema(app),
        "spec",
        "A",
        id="S_001",
        x=3,
    )
    assert need["x"] is None
    assert build_warnings(app) == [_undeclared(None, "S_001", "spec", 3)]


def test_its_own_export_imports_silently(make_app: Any, tmp_path: Path) -> None:
    """The needs.json of a project with fields declared on need types alone holds
    each of them on every need, ``None`` where the need's type does not declare it:
    imported, and read as external needs, by a project of the same configuration, it
    gives no warning, and each need holds what it held."""
    types = _types(
        req={"fields": {"x": {"schema": {"type": "integer"}}}},
        spec={"fields": {"y": {"schema": {"type": "string"}}}},
    )
    index = (
        ".. req:: A\n   :id: R_001\n   :x: 1\n\n"
        ".. spec:: B\n   :id: S_001\n   :y: s\n\n"
        ".. test:: C\n   :id: T_001\n"
    )
    first = tmp_path / "first"
    first.mkdir()
    (first / "conf.py").write_text(_conf(types), encoding="utf-8")
    (first / "index.rst").write_text("Case\n====\n\n" + index, encoding="utf-8")
    app = make_app("needs", srcdir=first)
    app.build()
    assert build_warnings(app) == []
    exported = Path(app.outdir, "needs.json")
    app.cleanup()

    second = tmp_path / "second"
    second.mkdir()
    (second / "exported.json").write_text(
        exported.read_text(encoding="utf-8"), encoding="utf-8"
    )
    external = (
        "needs_external_needs = [{'base_url': 'http://example.org', "
        f"'json_path': {str(second / 'exported.json')!r}, 'id_prefix': 'E_'}}]\n"
    )
    (second / "conf.py").write_text(
        _conf(types, None, None, external), encoding="utf-8"
    )
    (second / "index.rst").write_text(
        "Case\n====\n\n.. needimport:: exported.json\n   :id_prefix: M_\n",
        encoding="utf-8",
    )
    app = make_app("needs", srcdir=second)
    app.build()
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    held = {"R_001": (1, None), "S_001": (None, "s"), "T_001": (None, None)}
    for prefix in ("M_", "E_"):
        assert {
            k.removeprefix(prefix): (v["x"], v["y"])
            for k, v in needs.items()
            if k.startswith(prefix)
        } == held, prefix


def test_a_derived_value_from_outside_is_dropped_where_undeclared(
    make_app: Any, tmp_path: Path
) -> None:
    """A derived field declared on need types alone is absent on every other type for
    a need from outside too: a value a needs.json gives it there -- an edited file,
    or another project's -- is dropped with the warning; on a type that declares it,
    the value is kept, as data."""
    types = _types(
        req={
            "fields": {
                "dv": {
                    "schema": {"type": "integer"},
                    "derive": {"kind": "copy", "field": "effort"},
                }
            }
        },
        doc={},
    )
    fields = {"effort": {"schema": {"type": "integer"}, "nullable": True}}
    index = (
        ".. req:: A\n   :id: R_001\n   :effort: 3\n\n"
        ".. spec:: B\n   :id: S_001\n\n"
        ".. doc:: C\n   :id: D_001\n"
    )
    first = tmp_path / "first"
    first.mkdir()
    (first / "conf.py").write_text(_conf(types, fields), encoding="utf-8")
    (first / "index.rst").write_text("Case\n====\n\n" + index, encoding="utf-8")
    app = make_app("needs", srcdir=first)
    app.build()
    assert build_warnings(app) == []
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    app.cleanup()
    exported = data["versions"][data["current_version"]]["needs"]
    assert {k: v["dv"] for k, v in exported.items()} == {
        "R_001": 3,
        "S_001": None,
        "D_001": None,
    }
    # the file edited: a value on the types that do not declare the field
    exported["R_001"]["dv"] = 99
    exported["S_001"]["dv"] = 7
    exported["D_001"]["dv"] = 9

    second = tmp_path / "second"
    second.mkdir()
    (second / "edited.json").write_text(json.dumps(data), encoding="utf-8")
    external = (
        "needs_external_needs = [{'base_url': 'http://example.org', "
        f"'json_path': {str(second / 'edited.json')!r}, 'id_prefix': 'E_'}}]\n"
    )
    (second / "conf.py").write_text(
        _conf(types, fields, None, external), encoding="utf-8"
    )
    (second / "index.rst").write_text(
        "Case\n====\n\n.. needimport:: edited.json\n   :id_prefix: M_\n",
        encoding="utf-8",
    )
    app = make_app("needs", srcdir=second)
    app.build()
    assert build_warnings(app) == [
        _undeclared(None, "E_D_001", "doc", 9, "dv"),
        _undeclared(None, "E_S_001", "spec", 7, "dv"),
        _undeclared(4, "M_D_001", "doc", 9, "dv"),
        _undeclared(4, "M_S_001", "spec", 7, "dv"),
    ]
    needs = SphinxNeedsData(app.env).get_needs_view()
    for prefix in ("M_", "E_"):
        assert {
            k.removeprefix(prefix): v["dv"]
            for k, v in needs.items()
            if k.startswith(prefix)
        } == {"R_001": 99, "S_001": None, "D_001": None}, prefix


# -- one name, one shape: who sets it, and what disagrees --------------------------

SHAPE_TYPES = _types(
    a={
        "fields": {
            "d1": {"schema": {"type": "integer"}},
            "d2": {"schema": {"type": "integer"}},
            "d3": {},
            "d5": {"schema": {"type": "array", "items": {"type": "string"}}},
            "d7": {"schema": {"type": "integer"}, "nullable": False, "default": 0},
            "d10": {"schema": {"type": "integer"}},
            "d8": {"schema": {"type": "str"}},
        },
        "links": {"d4": {}},
    },
    b={
        "fields": {
            "d1": {"schema": {"type": "string"}},
            "d2": {"default": 3},
            "d3": {"description": "a d3"},
            "d4": {"schema": {"type": "string"}},
            "d5": {"schema": {"type": "array", "items": {"type": "integer"}}},
            "d7": {},
            "d8": {"schema": {"type": "integer"}},
        }
    },
    c={"inherits": "a", "fields": {"d10": {"schema": {"type": "string"}}}},
    z={"fields": {"d1": {"schema": {"type": "string"}}}},
    u={"inherits": "nosuch"},
)

SHAPE_INDEX = """\
.. a:: A
   :id: A_001
   :d1: 1
   :d2: 2
   :d5: x, y
   :d10: 4

.. b:: B
   :id: B_001
   :d1: three
   :d2: 5
   :d4: w
   :d5: 1, 2
   :d7: 9

.. b:: B2
   :id: B_002

.. c:: C
   :id: C_001
   :d1: 8
   :d10: 7

.. z:: Z
   :id: Z_001
   :d1: q

.. u:: U
   :id: U_001
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(_conf(SHAPE_TYPES), SHAPE_INDEX)],
    indirect=True,
)
def test_the_first_declaration_sets_the_shape(test_app: Any) -> None:
    """The first declaration of a type without a declaring ancestor -- in the order a
    parent comes before its children -- that gives a ``schema`` ``type`` sets the
    field's type and items' type; one that gives none takes it; one of another type
    is reported, naming the type that set it, and does not declare the field, whose
    values on that type's needs are then refused; a field no such declaration gives a
    type is refused on every entry, and does not exist; a type that is no field's
    sets nothing, and its entry does not declare the field. A child narrows its parent,
    and a type keeps its own ``nullable`` and ``default``. The walk's findings come
    first, then those of the shape, then those of each entry."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Need type 'u' inherits 'nosuch', which is not a need type; its "
        "inherits is ignored. [needs.type_inherits]",
        _shape("b", "d1", "string", "integer", "a"),
        _shape("z", "d1", "string", "integer", "a"),
        _untyped("a", "d3"),
        _untyped("b", "d3"),
        _conflict(
            "needs_types['b'].fields['d5'] cannot be declared with type 'array' "
            "(items 'integer'): its type is 'array' (items 'string') on every need "
            "type, as need type 'a' declares it"
        ),
        _conflict(
            "needs_types['a'].fields['d8'] cannot be declared: Invalid schema: Field "
            "schema has invalid type 'str'. Must be one of ['array', 'boolean', "
            "'integer', 'number', 'string']"
        ),
        _conflict(
            "needs_types['a'].links['d4'] declares 'd4', which is a field, not a link "
            "type"
        ),
        _conflict(
            "needs_types['c'].fields['d10'] cannot be declared with type 'string' "
            "(items None): its type is 'integer' (items None) on every need type"
        ),
        _undeclared(11, "B_001", "b", "three", "d1"),
        _undeclared(11, "B_001", "b", "1, 2", "d5"),
        _undeclared(27, "Z_001", "z", "q", "d1"),
    ]
    needs = _needs(app)
    assert {
        k: (v["d1"], v["d2"], v["d4"], v["d5"], v["d7"], v["d10"])
        for k, v in needs.items()
    } == {
        "A_001": (1, 2, None, ["x", "y"], 0, 4),
        "B_001": (None, 5, "w", None, 9, None),
        "B_002": (None, 3, None, None, None, None),
        "C_001": (8, None, None, None, 0, 7),
        "Z_001": (None, None, None, None, None, None),
        "U_001": (None, None, None, None, None, None),
    }
    assert all("d3" not in need for need in needs.values())
    properties = _properties(app)
    assert "d3" not in properties
    assert properties["d2"]["description"] == "Declared by need types 'a', 'b'"
    assert properties["d7"]["type"] == ["integer", "null"]
    assert _field(app, "b", "d2").type == "integer"
    assert _field(app, "b", "d8").type == "integer"
    assert _field(app, "a", "d8").directive_option is False
    assert _schema(app).global_declaration("d3") is None


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    a={
                        "fields": {
                            "e1": {"schema": {"type": "array"}},
                            "e2": {
                                "schema": {"type": "array", "items": {"type": "string"}}
                            },
                            "m1": {},
                        }
                    },
                    b={
                        "fields": {
                            "e1": {
                                "schema": {"type": "array", "items": {"type": "string"}}
                            },
                            "e2": {"schema": {"type": "array"}},
                        }
                    },
                    c={
                        "inherits": "a",
                        "fields": {"m1": {"schema": {"type": "integer"}}},
                    },
                )
            ),
            ".. a:: A\n   :id: A_001\n   :e1: p\n\n"
            ".. b:: B\n   :id: B_001\n   :e1: q\n   :e2: r\n",
        )
    ],
    indirect=True,
)
def test_the_first_declaration_of_an_array_gives_its_items(test_app: Any) -> None:
    """The first declaration of a field that is an array gives its items' type: one
    that gives none is refused with the text a ``needs_fields`` entry gets; a later
    one that gives none takes the agreed items. A child never sets the shape: the
    field of an untyped declaration whose child gives a type does not exist."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _conflict(
            "needs_types['a'].fields['e1'] cannot be declared: Invalid schema: "
            '"items" is a required property'
        ),
        _untyped("a", "m1"),
        _untyped("c", "m1"),
        _undeclared(4, "A_001", "a", "p", "e1"),
    ]
    assert {k: (v["e1"], v["e2"]) for k, v in _needs(app).items()} == {
        "A_001": (None, None),
        "B_001": (["q"], ["r"]),
    }
    assert _field(app, "b", "e2").schema == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert _schema(app).global_declaration("m1") is None


INHERITED_TYPES = _types(
    req={"fields": {"x": {"schema": {"type": "integer", "minimum": 0}}}},
    sreq={
        "inherits": "req",
        "fields": {"x": {"schema": {"maximum": 10}, "nullable": False, "default": 5}},
    },
    wide={"inherits": "req", "fields": {"x": {"schema": {"minimum": -5}}}},
    spec={"fields": {"x": {"default": 2}}},
)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(INHERITED_TYPES),
            ".. req:: A\n   :id: R_001\n   :x: 3\n\n"
            ".. sreq:: B\n   :id: SR_001\n\n"
            ".. wide:: C\n   :id: W_001\n   :x: 3\n\n"
            ".. spec:: D\n   :id: S_001\n\n"
            ".. impl:: E\n   :id: I_001\n   :x: 1\n",
        )
    ],
    indirect=True,
)
def test_a_child_narrows_and_a_sibling_agrees(test_app: Any) -> None:
    """A child of a declaring type declares the field as its parent does, and narrows
    it; a child's entry that widens is reported and the child keeps its parent's
    declaration, which it still declares; a sibling declares the field anew, of the
    agreed type."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['wide'].fields['x'] widens the field as need type 'req' "
        "declares it: Child 'minimum' -5 is less than parent 'minimum' 0. "
        "[needs.type_widening]",
        _undeclared(18, "I_001", "impl", "1"),
    ]
    assert {k: v["x"] for k, v in _needs(app).items()} == {
        "R_001": 3,
        "SR_001": 5,
        "W_001": 3,
        "S_001": 2,
        "I_001": None,
    }
    assert sorted(dict(_schema(app).type_declarations("x"))) == [
        "req",
        "spec",
        "sreq",
        "wide",
    ]
    assert _field(app, "wide", "x").schema == {"type": "integer", "minimum": 0}


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    req={"fields": {"x": {"schema": {"type": "string"}}}},
                    spec={"fields": {"x": {}}, "links": {"links": {}}},
                )
            ),
            ".. req:: A\n   :id: R_001\n\n.. spec:: B\n   :id: S_001\n   :x: kept\n"
            "   :links: R_001\n\n.. impl:: C\n   :id: I_001\n   :x: v\n",
        )
    ],
    indirect=True,
)
def test_an_empty_entry_declares(test_app: Any) -> None:
    """An entry that changes nothing declares the field for its type, of the agreed
    type; a field every type has stays as declared."""
    app = test_app
    app.build()
    assert build_warnings(app) == [_undeclared(12, "I_001", "impl", "v")]
    assert {k: (v["x"], v["links"]) for k, v in _needs(app).items()} == {
        "R_001": (None, []),
        "S_001": ("kept", ["R_001"]),
        "I_001": (None, []),
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    req={
                        "fields": {"n": {"schema": {"type": "integer", "maximum": 9}}}
                    },
                    impl={
                        "inherits": "req",
                        "fields": {"n": {"schema": {"maximum": 99}}},
                    },
                    test={"inherits": "req", "fields": {"n": {"default": "abc"}}},
                    spec={"fields": {"n": {"schema": {"type": "string"}}}},
                )
            ),
            ".. impl:: A\n   :id: I_001\n   :n: 5\n\n"
            ".. test:: B\n   :id: T_001\n   :n: 6\n\n"
            ".. spec:: C\n   :id: S_001\n   :n: 7\n",
        )
    ],
    indirect=True,
)
def test_a_refused_entry_still_declares(test_app: Any) -> None:
    """An entry the resolver cannot use -- it widens, or its default cannot be used --
    declares its field all the same: the type keeps the declaration before it. An
    entry refused for the field's shape does not."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _shape("spec", "n", "string", "integer", "req"),
        "WARNING: needs_types['impl'].fields['n'] widens the field as need type 'req' "
        "declares it: Child 'maximum' 99 is greater than parent 'maximum' 9. "
        "[needs.type_widening]",
        _conflict(
            "needs_types['test'].fields['n'] sets a 'default' that cannot be used: "
            "Cannot convert 'abc' to integer"
        ),
        _undeclared(12, "S_001", "spec", "7", "n"),
    ]
    assert {k: v["n"] for k, v in _needs(app).items()} == {
        "I_001": 5,
        "T_001": 6,
        "S_001": None,
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    f1={"fields": {"k5": {"schema": {"type": "integer"}}}},
                    f2={"fields": {"k5": {"schema": {"type": "string"}}}},
                    f3={
                        "inherits": "f2",
                        "fields": {"k5": {"schema": {"type": "string"}}},
                    },
                    f4={"inherits": "f2", "fields": {"k5": {}}},
                    f5={"inherits": "f2"},
                )
            ),
            ".. f2:: A\n   :id: F2_001\n   :k5: s\n\n"
            ".. f3:: B\n   :id: F3_001\n   :k5: hello\n\n"
            ".. f3:: C\n   :id: F3_002\n   :k5: 12\n\n"
            ".. f4:: D\n   :id: F4_001\n   :k5: 4\n\n"
            ".. f5:: E\n   :id: F5_001\n   :k5: 12\n",
        )
    ],
    indirect=True,
)
def test_a_child_of_a_refused_declaration_is_a_declaration_of_its_own(
    test_app: Any,
) -> None:
    """An entry refused for the field's shape declares nothing, so a child's entry
    under it is a declaration of its own: one of the refused type is refused too,
    and does not declare the field -- its needs are kept, the value dropped; an
    empty one takes the agreed type; a child without an entry does not declare it."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _shape("f2", "k5", "string", "integer", "f1"),
        _shape("f3", "k5", "string", "integer", "f1"),
        _undeclared(4, "F2_001", "f2", "s", "k5"),
        _undeclared(8, "F3_001", "f3", "hello", "k5"),
        _undeclared(12, "F3_002", "f3", "12", "k5"),
        _undeclared(20, "F5_001", "f5", "12", "k5"),
    ]
    assert {k: v["k5"] for k, v in _needs(app).items()} == {
        "F2_001": None,
        "F3_001": None,
        "F3_002": None,
        "F4_001": 4,
        "F5_001": None,
    }
    assert _properties(app)["k5"]["description"] == "Declared by need types 'f1', 'f4'"


REQUIRED_TYPES = _types(
    req={
        "fields": {
            "must": {"schema": {"type": "string"}, "nullable": False},
            "s": {
                "schema": {"type": "string", "minLength": 1},
                "nullable": False,
                "default": "A",
            },
        }
    }
)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(REQUIRED_TYPES),
            ".. req:: A\n   :id: R_001\n   :must: v\n\n"
            ".. req:: B\n   :id: R_002\n\n"
            ".. spec:: C\n   :id: S_001\n\n"
            ".. needextend:: R_001\n   :-must:\n",
        )
    ],
    indirect=True,
)
def test_required_on_the_types_that_declare_it(test_app: Any) -> None:
    """A field a type declares not nullable, without a default, must be set on the
    needs of that type alone; a need of a type that does not declare it holds
    ``None``, which is not validated. A needextend deleting it on a declaring need
    empties it as the type declares it."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:8: WARNING: Need could not be created: Field 'must' is not "
        "nullable, but no value or default was given. [needs.create_need]",
    ]
    assert {k: (v["must"], v["s"]) for k, v in _needs(app).items()} == {
        "R_001": ("", "A"),
        "S_001": (None, None),
    }


# -- an extension's field, and the readers of the configuration ---------------------


@pytest.mark.skipif(
    importlib.util.find_spec("sphinx_test_reports") is None,
    # sphinx-test-reports is a workspace sibling, not a dependency: the release
    # workflow's compat cell runs this suite against the released dependencies
    # alone, where it is absent, and this is the only test that loads it (the
    # skip must sit on the test, not in it: the app fixture loads the extension).
    reason="sphinx-test-reports is not installed",
)
@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            'extensions = ["sphinx_needs", "sphinx_test_reports"]\n'
            "needs_build_json = True\n"
            "needs_types = "
            + repr(
                _types(
                    spec={
                        "fields": {
                            "suite": {"schema": {"type": "string", "minLength": 1}}
                        }
                    }
                )
            )
            + "\n",
        )
    ],
    indirect=True,
)
def test_an_extensions_field_is_declared_on_its_types_and_the_types_naming_it(
    test_app: Any,
) -> None:
    """A field an extension declares on its own need types alone (sphinx-test-reports'
    ``suite``, on its test suites and test cases, #2372) stays the extension's, however
    late the extension registers it: a need type's entry of it is a narrowing, and
    declares it on that type too; a type with no entry does not declare it."""
    app = test_app
    app.build()
    schema = _schema(app)
    assert not schema.is_project_field("suite")
    assert schema.declaring_types("suite") == {"testsuite", "testcase", "spec"}
    for need_type in ("testsuite", "testcase", "spec"):
        field = _field(app, need_type, "suite")
        assert (field.directive_option, field.allow_extend) == (True, True), need_type
    field = _field(app, "req", "suite")
    assert (field.directive_option, field.allow_extend) == (False, False)
    assert _field(app, "spec", "suite").schema["minLength"] == 1


#: a ``needs_string_links`` entry, a card layout and a variant option naming ``x``
READERS_CONF = """
needs_string_links = {
    "xl": {
        "regex": r"^(?P<value>[A-Z]+-\\d+)$",
        "link_url": "https://tracker.example.com/{{value}}",
        "link_name": "T:{{value}}",
        "options": ["x"],
    }
}
needs_card_layouts = {"card": {"footer": ["field:x"]}}
needs_variant_options = ["x"]
"""

READERS_TYPES = _types(req={"fields": {"x": {"schema": {"type": "string"}}}})


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(READERS_TYPES, None, None, READERS_CONF),
            ".. req:: A\n   :id: R_001\n   :x: AB-1\n",
        )
    ],
    indirect=True,
)
def test_the_configuration_readers_know_the_name(test_app: Any) -> None:
    """The readers of the configuration that run before the schema is built --
    ``needs_string_links``, ``needs_card_layouts`` and the check of
    ``needs_variant_options`` -- take a field a need type declares for a field."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        'WARNING: Config option "needs_variant_options" is deprecated. Please use '
        '"needs_fields" with "parse_variants" instead. [needs.deprecated]',
    ]
    glob = _schema(app).global_declaration("x")
    assert glob is not None
    assert glob.parse_variants is True
    assert _needs(app)["R_001"]["x"] == "AB-1"


def test_a_filter_data_of_the_same_name_is_refused(
    make_app: Any, tmp_path: Path
) -> None:
    """``needs_filter_data`` may not name a field a need type declares, as it may not
    name one of ``needs_fields``."""
    (tmp_path / "conf.py").write_text(
        _conf(READERS_TYPES, None, None, "needs_filter_data = {'x': 'v'}\n"),
        encoding="utf-8",
    )
    (tmp_path / "index.rst").write_text("Case\n====\n", encoding="utf-8")
    with pytest.raises(NeedsConfigException) as exc_info:
        make_app("needs", srcdir=tmp_path)
    assert str(exc_info.value) == (
        "Same name for external filter and field: x. This is not allowed."
    )


# -- derive in a need type's entry ----------------------------------------------------

FOLD_FIELDS = {
    "effort": {"schema": {"type": "number"}, "nullable": True},
    "total": {
        "schema": {"type": "number"},
        "nullable": False,
        "derive_by_type": {
            "story": {"kind": "sum", "field": "effort", "over": "links"}
        },
    },
}

FOLD_TYPES = _types(
    task={
        "fields": {
            "total": {"derive": {"kind": "copy", "field": "effort"}},
            "score": {
                "schema": {"type": "number"},
                "derive": {"kind": "copy", "field": "effort"},
            },
        }
    },
    subtask={"inherits": "task"},
    story={
        "fields": {
            "total": {"derive": {"kind": "sum", "field": "total", "over": "links"}},
            "score": {
                "schema": {"type": "number"},
                "derive": {"kind": "sum", "field": "score", "over": "links"},
            },
        }
    },
    bug={"fields": {"score": {"schema": {"type": "number"}, "nullable": False}}},
    doc={},
)

FOLD_INDEX = """\
.. task:: T
   :id: T_001
   :effort: 3

.. subtask:: ST
   :id: ST_001
   :effort: 2

.. story:: S
   :id: S_001
   :links: T_001, ST_001

.. bug:: B
   :id: B_001
   :total: 4
   :score: 6

.. doc:: D
   :id: D_001
   :score: 1
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(_conf(FOLD_TYPES, FOLD_FIELDS), FOLD_INDEX)],
    indirect=True,
)
def test_a_derive_in_a_need_types_entry(test_app: Any) -> None:
    """A ``derive`` in a type's entry is the field's ``derive_by_type`` entry for the
    type, and its children's (a child's own rule overrides it): a field
    ``needs_fields`` declares is then derived on every type, as with
    ``derive_by_type``, and a field declared on need types alone is derived on every
    type that declares it -- one that declares it without a rule is reported, and
    does not declare it. A type's own rule beside a ``derive_by_type`` entry for the
    type is reported, and the ``derive_by_type`` one used."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['story'].fields['total'] sets 'derive', and "
        "needs_fields['total'].derive_by_type['story'] another rule for the same "
        "type; the need type's rule is ignored for it (the need types inheriting "
        "from it still read it) [needs.config]",
        _conflict(
            "needs_types['bug'].fields['score'] cannot be declared without a "
            "'derive': it is derived on every need type that declares it, as need "
            "type 'task' declares it"
        ),
        "<srcdir>/index.rst:16: WARNING: Field 'total' is derived (with no rule on "
        "need type 'bug') and cannot be set in a need; the value '4' is ignored "
        "[needs.derive_authored]",
        _undeclared(16, "B_001", "bug", "6", "score"),
        _undeclared(21, "D_001", "doc", "1", "score"),
    ]
    assert {k: (v["total"], v["score"]) for k, v in _needs(app).items()} == {
        "T_001": (3.0, 3.0),
        "ST_001": (2.0, 2.0),
        "S_001": (5.0, 5.0),
        "B_001": (0.0, None),
        "D_001": (0.0, None),
    }
    score = _properties(app)["score"]
    assert (score["type"], score["readOnly"], score["description"]) == (
        ["number", "null"],
        True,
        "Declared by need types 'task', 'story'",
    )
    schema = _schema(app)
    for name in ("total", "score"):
        glob = schema.global_declaration(name)
        assert glob is not None
        assert sorted(glob.derive_by_type or {}) == ["story", "subtask", "task"], name


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    task={
                        "fields": {
                            "p": {
                                "schema": {"type": "string"},
                                "derive": {"kind": "copy", "field": "q"},
                            },
                            "q": {
                                "schema": {"type": "string"},
                                "derive": {"kind": "copy", "field": "p"},
                            },
                            "r": {
                                "schema": {"type": "string"},
                                "derive": {"kind": "copy", "field": "nosuch"},
                            },
                        }
                    },
                    story={
                        "fields": {
                            "p": {
                                "schema": {"type": "string"},
                                "derive": {"kind": "copy", "field": "title"},
                            }
                        }
                    },
                )
            ),
            ".. task:: A\n   :id: T_001\n\n.. story:: b\n   :id: S_001\n",
        )
    ],
    indirect=True,
)
def test_the_rules_of_a_need_types_entry_are_checked(test_app: Any) -> None:
    """The rules a type's entry gives are checked with the field's other rules, before
    any need is read, and reported naming the entry: a cycle, a role naming no
    field; another type's rule of the field is unaffected."""
    app = test_app
    app.build()
    tail = (
        "; the field cannot be set in a need or by a needextend, and on need type "
        "'task' holds its empty value [needs.derive_invalid]"
    )
    assert build_warnings(app) == [
        "WARNING: Invalid derive of field 'p': needs_types['task'].fields['p'].derive: "
        "kind 'copy': the role 'field' reads 'q', whose rule reads this field back "
        "(p -> q -> p), so no need can compute it" + tail,
        "WARNING: Invalid derive of field 'q': needs_types['task'].fields['q'].derive: "
        "kind 'copy': the role 'field' reads 'p', whose rule reads this field back "
        "(q -> p -> q), so no need can compute it" + tail,
        "WARNING: Invalid derive of field 'r': needs_types['task'].fields['r'].derive: "
        "kind 'copy': the role 'field' names 'nosuch', which is not a field, a link "
        "type or the back links of one" + tail,
    ]
    assert {k: (v["p"], v["q"], v["r"]) for k, v in _needs(app).items()} == {
        "T_001": (None, None, None),
        "S_001": ("b", None, None),
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    req={
                        "fields": {
                            "grade": {
                                "schema": {"type": "string", "enum": ["a", "b"]},
                                "derive": {"kind": "copy", "field": "title"},
                            },
                            "lvl": {
                                "schema": {"type": "integer"},
                                "derive": {
                                    "kind": "max",
                                    "field": "lvl",
                                    "over": "links",
                                    "transitive": True,
                                    "include_self": True,
                                },
                            },
                        }
                    }
                )
            ),
            ".. req:: T\n   :id: R_001\n",
        )
    ],
    indirect=True,
)
def test_a_derived_field_of_need_types_alone_takes_no_enum(test_app: Any) -> None:
    """A derived field declared on need types alone takes no ``enum``: its rules are
    checked against a declaration without one; the entry is reported, the rule still
    applies. A rule of such a field reading itself is a cycle on the need, as any
    rule's."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _conflict(
            "needs_types['req'].fields['grade'] adds an 'enum', but 'grade' is derived "
            "(by need type), and a derived field declared on need types alone takes "
            "no 'enum'"
        ),
        "<srcdir>/index.rst:4: WARNING: derive rule 'max' for option 'lvl' is on a "
        "cycle: 'lvl' on need 'R_001'; the field is left empty [needs.derive_cycle]",
    ]
    assert {k: (v["grade"], v["lvl"]) for k, v in _needs(app).items()} == {
        "R_001": ("T", None)
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    a={"fields": {"k": {"schema": {"type": "integer"}}}},
                    c={
                        "inherits": "a",
                        "fields": {
                            "k": {"derive": {"kind": "copy", "field": "n"}},
                            "status": {"derive": {"kind": "copy", "field": "title"}},
                        },
                    },
                    spec={
                        "links": {
                            "blocks": {
                                "derive": {"kind": "links", "where": "type == 'req'"}
                            }
                        }
                    },
                ),
                {"n": {"schema": {"type": "integer"}, "nullable": True}},
                {"blocks": BLOCKS},
            ),
            ".. req:: A\n   :id: R_001\n\n.. spec:: B\n   :id: S_001\n\n"
            ".. impl:: C\n   :id: I_001\n\n"
            ".. c:: D\n   :id: C_001\n   :k: 5\n   :n: 6\n",
        )
    ],
    indirect=True,
)
def test_what_a_derive_in_an_entry_reaches(test_app: Any) -> None:
    """A ``derive`` in a type's ``links`` entry derives a link type ``needs_links``
    declares, on every type; a ``derive`` on a core field is reported and ignored, as
    in ``needs_fields``; a child's ``derive`` of a field its parent declares on need
    types alone, without a rule, is reported and ignored: the field stays authorable."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Invalid derive of field 'status': "
        "needs_types['c'].fields['status'].derive: a core field cannot carry a derive "
        "rule in this release; the rule is ignored [needs.derive_invalid]",
        _conflict(
            "needs_types['c'].fields['k'] cannot be declared with a 'derive': it is "
            "not derived on every need type that declares it, as need type 'a' "
            "declares it"
        ),
    ]
    needs = _needs(app)
    assert {k: v["blocks"] for k, v in needs.items()} == {
        "R_001": [],
        "S_001": ["R_001"],
        "I_001": [],
        "C_001": [],
    }
    assert needs["C_001"]["k"] == 5
    blocks = _schema(app).global_declaration("blocks")
    assert blocks is not None
    assert sorted(blocks.derive_by_type or {}) == ["spec"]


# -- the fold's precedence, the walk, a link type under fields, a schema by hand ------


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    task={
                        "fields": {
                            "total": {"derive": {"kind": "copy", "field": "effort"}},
                            "ov": {
                                "schema": {"type": "number"},
                                "derive": {"kind": "copy", "field": "effort"},
                            },
                        }
                    },
                    subtask={
                        "inherits": "task",
                        "fields": {
                            "ov": {"derive": {"kind": "copy", "field": "other"}}
                        },
                    },
                ),
                {
                    "effort": {"schema": {"type": "number"}},
                    "other": {"schema": {"type": "number"}},
                    "total": {
                        "schema": {"type": "number"},
                        "nullable": True,
                        "derive_by_type": {
                            "subtask": {"kind": "copy", "field": "other"}
                        },
                    },
                },
            ),
            ".. task:: a\n   :id: T_001\n   :effort: 3\n   :other: 5\n\n"
            ".. subtask:: b\n   :id: ST_001\n   :effort: 2\n   :other: 9\n",
        )
    ],
    indirect=True,
)
def test_an_inherited_rule_gives_way(test_app: Any) -> None:
    """A rule a type inherits gives way, silently, to an explicit
    ``derive_by_type`` entry for the child, and to the child's own ``derive``."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert {k: (v["total"], v["ov"]) for k, v in _needs(app).items()} == {
        "T_001": (3.0, 3.0),
        "ST_001": (9.0, 9.0),
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                [
                    {"directive": "k", "title": "K", "prefix": "K_", "inherits": "m"},
                    {
                        "directive": "r1",
                        "title": "R",
                        "prefix": "R_",
                        "fields": {"x": {"schema": {"type": "string"}}},
                    },
                    {
                        "directive": "m",
                        "title": "M",
                        "prefix": "M_",
                        "fields": {"x": {"schema": {"type": "integer"}}},
                    },
                    {
                        "directive": "p",
                        "title": "P",
                        "prefix": "P_",
                        "inherits": "q",
                        "fields": {"y": {"schema": {"type": "integer"}}},
                    },
                    {
                        "directive": "q",
                        "title": "Q",
                        "prefix": "Q_",
                        "inherits": "p",
                        "fields": {"y": {}},
                    },
                ]
            ),
            ".. k:: a\n   :id: K_001\n   :x: 1\n\n.. m:: c\n   :id: M_001\n   :x: 2\n\n"
            ".. p:: d\n   :id: P_001\n   :y: 3\n\n.. q:: e\n   :id: Q_001\n   :y: 4\n",
        )
    ],
    indirect=True,
)
def test_the_walk_decides_the_roots(test_app: Any) -> None:
    """The roots are read in the walk's order, not the configured one: a parent given
    after its child sets the shape before a type given between them; the two members
    of a broken ``inherits`` cycle are both roots, the untyped one taking the other's
    type."""
    app = test_app
    app.build()
    assert {k: (v["x"], v["y"]) for k, v in _needs(app).items()} == {
        "K_001": (1, None),
        "M_001": (2, None),
        "P_001": (None, 3),
        "Q_001": (None, 4),
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            CONF + "needs_extra_links = [{'option': 'blocks', 'incoming': 'in', "
            "'outgoing': 'out'}]\n"
            + "needs_types = "
            + repr(_types(spec={"fields": {"blocks": {}}}))
            + "\n"
        )
    ],
    indirect=True,
)
def test_a_link_type_under_fields_is_no_field(test_app: Any) -> None:
    """A ``needs_extra_links`` name under a type's ``fields`` is a mis-tabled link
    type -- the configuration check does not take it for a field -- and the build goes
    on with the warning."""
    app = test_app
    app.build()
    assert _conflict(
        "needs_types['spec'].fields['blocks'] declares 'blocks', which is a link type, "
        "not a field"
    ) in build_warnings(app)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={
                        "fields": {
                            name: {"schema": {"type": "string"}}
                            for name in (
                                "links_back",
                                "parent_needs_back",
                                "blocks_back",
                            )
                        }
                    }
                ),
                links={"blocks": BLOCKS},
            ),
            ".. req:: A\n   :id: R_001\n\n"
            ".. req:: B\n   :id: R_002\n   :links: R_001\n   :blocks: R_001\n\n"
            ".. spec:: C\n   :id: S_001\n   :links: R_001\n   :links_back: x\n\n"
            "   .. req:: D\n      :id: R_003\n",
        )
    ],
    indirect=True,
)
def test_a_field_named_as_back_links_is_refused(test_app: Any) -> None:
    """#2301: a ``fields`` entry named as the back links of a link type -- of ``links``,
    of ``parent_needs``, of a ``needs_links`` type -- declares no field: it is one
    finding per entry, as a ``links`` entry of that name is, and the back links are
    computed on every need as without it, never validated against the entry's schema;
    the need directive has no option of the name (it used to take the value, and lose
    it to the back links)."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        *(
            _conflict(
                f"needs_types['spec'].fields[{name!r}] declares {name!r}, which is a "
                "link type's back links"
            )
            for name in ("links_back", "parent_needs_back", "blocks_back")
        ),
        "<srcdir>/index.rst:12: WARNING: Unknown option 'links_back' [needs.directive]",
    ]
    needs = _needs(app)
    assert {
        k: (v["links_back"], v["parent_needs_back"], v["blocks_back"])
        for k, v in needs.items()
    } == {
        "R_001": (["R_002", "S_001"], [], ["R_002"]),
        "R_002": ([], [], []),
        "S_001": ([], ["R_003"], []),
        "R_003": ([], [], []),
    }
    for name in ("links_back", "parent_needs_back", "blocks_back"):
        assert _schema(app).get_extra_field(name) is None, name
        assert _properties(app)[name]["field_type"] == "backlinks", name


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            CONF + "needs_extra_links = [{'option': 'blocks', 'incoming': 'in', "
            "'outgoing': 'out'}]\n"
            + "needs_types = "
            + repr(_types(spec={"fields": {"blocks_back": {}}}))
            + "\n",
            ".. req:: A\n   :id: R_001\n\n.. spec:: B\n   :id: S_001\n   :blocks: R_001\n",
        )
    ],
    indirect=True,
)
def test_a_field_named_as_extra_links_back_links_is_refused(test_app: Any) -> None:
    """A ``fields`` entry named as the back links of a ``needs_extra_links`` type is
    refused as the others are; the configuration check used to stop the build on it."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        'WARNING: Config option "needs_extra_links" is deprecated. Please use '
        '"needs_links" instead. [needs.deprecated]',
        _conflict(
            "needs_types['spec'].fields['blocks_back'] declares 'blocks_back', which is "
            "a link type's back links"
        ),
    ]
    assert _needs(app)["R_001"]["blocks_back"] == ["S_001"]
    assert _schema(app).get_extra_field("blocks_back") is None


def test_a_schema_not_told_its_types_projects_absence() -> None:
    """A schema built by hand and never told its need types still makes a field
    declared on need types alone absent on every other type."""
    schema = FieldsSchema()
    schema.add_extra_field(_open_field("x"), project=True)
    schema._localise("x", ["req"])
    absent = schema.for_type("spec").get_any_field("x")
    assert absent is not None
    assert (absent.directive_option, absent.allow_extend) == (False, False)
    assert schema.for_type("req").get_any_field("x") is schema.global_declaration("x")


DERIVED_NAMES_FIELDS = {
    "effort": {"schema": {"type": "integer"}, "nullable": True},
    "everywhere": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "title"},
    },
    "by_type": {
        "schema": {"type": "string"},
        "derive_by_type": {"spec": {"kind": "copy", "field": "title"}},
    },
}
DERIVED_NAMES_TYPES = _types(
    req={
        "fields": {
            "local_derived": {
                "schema": {"type": "integer"},
                "derive": {"kind": "copy", "field": "effort"},
            }
        }
    }
)
DERIVED_NAMES_LINKS = {"mentions": {"derive": {"kind": "content_links"}}}
DERIVED_NAMES_INDEX = (
    ".. req:: A\n   :id: R_001\n   :effort: 3\n\n.. spec:: B\n   :id: S_001\n"
)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(DERIVED_NAMES_TYPES, DERIVED_NAMES_FIELDS, DERIVED_NAMES_LINKS),
            DERIVED_NAMES_INDEX,
        )
    ],
    indirect=True,
)
def test_the_derived_names_are_one_set_for_every_need_type(test_app: Any) -> None:
    """``derived_names`` is every derived field and link type -- by ``derive``, by
    ``derive_by_type`` (derived on a type with no rule too), and declared on need types
    alone (derived on a type that does not declare it too) -- one set, the same object
    for each need type and the global view; a need refuses each, on every type."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    data = SphinxNeedsData(app.env)
    schema = data.get_schema()
    names = schema.derived_names
    assert names == {"everywhere", "by_type", "local_derived", "mentions"}
    assert schema.for_type("req") is not schema.for_type("spec")
    assert schema.for_type("req").derived_names is names
    assert schema.for_type("spec").derived_names is names
    assert schema.for_type(None).derived_names is names

    needs = data.get_needs_view()
    for need_id in ("R_001", "S_001"):
        for name in sorted(names):
            with pytest.raises(KeyError, match=r"Cannot set derived field"):
                needs[need_id][name] = None


def test_the_derived_names_of_a_schema_built_by_hand() -> None:
    """An unfrozen schema answers its derived names at each read; freezing fixes them,
    and a view of one need type made directly answers its own."""
    schema = FieldsSchema()
    schema.add_extra_field(_open_field("x"), project=True)
    assert schema.derived_names == frozenset()
    schema.add_extra_field(
        FieldSchema(
            name="d",
            schema={"type": "string"},
            derive=DeriveRule(kind="copy", field="title"),
        )
    )
    assert schema.derived_names == {"d"}
    schema.freeze()
    assert schema.derived_names is schema.derived_names
    assert schema.for_type("spec").derived_names is schema.derived_names
