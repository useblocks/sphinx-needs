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

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.api.need import generate_need
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsConfigException
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
        "needs_fields entry declares, and no need type gives it a 'schema' 'type'"
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
    type is refused on every entry, and does not exist. A child narrows its parent,
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
    assert _schema(app).global_declaration("d3") is None


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
        _undeclared(17, "I_001", "impl", "1"),
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
def test_an_extensions_field_is_never_declared_on_need_types_alone(
    test_app: Any,
) -> None:
    """A need type's entry of a field an extension registers is a narrowing of it,
    however late the extension registers it: the field stays the extension's, on
    every need type."""
    app = test_app
    app.build()
    schema = _schema(app)
    assert not schema.is_project_field("suite")
    for need_type in ("tr_case", "tr_suite", "req"):
        field = _field(app, need_type, "suite")
        assert (field.directive_option, field.allow_extend) == (True, True), need_type
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
needs_card_layouts = {"card": {"footer": ["x"]}}
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
        "type; the need type's rule is ignored [needs.config]",
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
