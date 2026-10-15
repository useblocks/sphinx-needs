"""A need type declares its fields: ``inherits``, ``fields`` and ``links`` on a
``needs_types`` entry.

``create_schema`` resolves the declarations as its last step: each type's declaration of
a field starts from the field's global declaration, takes its ancestors' entries from
the root down, then its own, each a narrowing of the one before. What cannot be used is
reported, one warning per reason, and ignored: ``needs.type_inherits`` (an unknown
parent, a cycle), ``needs.type_conflict`` (an entry that cannot be applied) and
``needs.type_widening`` (an entry that is not a narrowing). A ``needextend`` deleting a
field writes the empty value the need's type declares.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import WarningSubTypeDescription, WarningSubTypes
from sphinx_needs.needs import _inherits_order
from sphinx_needs.needs_schema import (
    FieldLiteralValue,
    FieldsSchema,
    LinksLiteralValue,
    NeedLink,
)
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

TOML_CONF = CONF + 'needs_from_toml = "ubproject.toml"\n'

#: the default need types but ``need``, as a table keyed by directive
BASE_TYPES: dict[str, dict[str, Any]] = {
    "req": {"title": "Requirement", "prefix": "R_"},
    "spec": {"title": "Specification", "prefix": "S_"},
    "impl": {"title": "Implementation", "prefix": "I_"},
    "test": {"title": "Test Case", "prefix": "T_"},
}


def _types(**declarations: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """``BASE_TYPES``, each named type with its declarations added."""
    return {
        name: {**entry, **declarations.get(name, {})}
        for name, entry in BASE_TYPES.items()
    }


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


def _project(conf: str, index: str = "", **files: str) -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Case\n====\n\n" + index),
            *((Path(name), text) for name, text in files.items()),
        ],
    }


def _toml_project(toml: str, index: str = "") -> dict[str, Any]:
    return _project(TOML_CONF, index, **{"ubproject.toml": toml})


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


# -- the warnings ------------------------------------------------------------------------


def test_the_three_codes_are_listed() -> None:
    """The codes are in the list the documentation renders for ``suppress_warnings``."""
    assert {"type_conflict", "type_inherits", "type_widening"} <= set(
        get_args(WarningSubTypes)
    )
    assert WarningSubTypeDescription["type_inherits"] == (
        "A need type's inherits names no need type, or is on a cycle; it is ignored and "
        "the type has no parent"
    )
    assert WarningSubTypeDescription["type_conflict"] == (
        "A need type's declaration of a field or link type cannot be applied to it; "
        "the declaration is ignored"
    )
    assert WarningSubTypeDescription["type_widening"] == (
        "A need type's declaration of a field or link type widens the declaration it "
        "inherits; the declaration is ignored"
    )


# -- inherits: the order the types resolve in ---------------------------------------------


def _inherits(*pairs: tuple[str, str | None]) -> dict[str, dict[str, Any]]:
    return {
        name: {} if parent is None else {"inherits": parent} for name, parent in pairs
    }


@pytest.mark.parametrize(
    ("types", "order", "parents", "findings"),
    [
        pytest.param(
            _inherits(("req", None), ("spec", "req")),
            ["req", "spec"],
            {"spec": "req"},
            [],
            id="plain",
        ),
        pytest.param(
            _inherits(("spec", "req"), ("impl", "spec"), ("req", None)),
            ["req", "spec", "impl"],
            {"spec": "req", "impl": "spec"},
            [],
            id="parent-declared-later",
        ),
        pytest.param(
            _inherits(("a", "b"), ("b", "a"), ("c", None)),
            ["b", "a", "c"],
            {},
            [
                "Need type 'a' inherits 'b' on a cycle (a -> b -> a); its inherits is "
                "ignored.",
                "Need type 'b' inherits 'a' on a cycle (a -> b -> a); its inherits is "
                "ignored.",
            ],
            id="two-cycle",
        ),
        pytest.param(
            _inherits(("t", "a"), ("a", "b"), ("b", "c"), ("c", "a")),
            ["c", "b", "a", "t"],
            {"t": "a"},
            [
                "Need type 'a' inherits 'b' on a cycle (a -> b -> c -> a); its "
                "inherits is ignored.",
                "Need type 'b' inherits 'c' on a cycle (a -> b -> c -> a); its "
                "inherits is ignored.",
                "Need type 'c' inherits 'a' on a cycle (a -> b -> c -> a); its "
                "inherits is ignored.",
            ],
            id="three-cycle-with-a-tail",
        ),
        pytest.param(
            _inherits(("a", "a")),
            ["a"],
            {},
            [
                "Need type 'a' inherits 'a' on a cycle (a -> a); its inherits is "
                "ignored."
            ],
            id="self",
        ),
        pytest.param(
            _inherits(("e", "nope"), ("f", "e")),
            ["e", "f"],
            {"f": "e"},
            [
                "Need type 'e' inherits 'nope', which is not a need type; its "
                "inherits is ignored."
            ],
            id="unknown-with-a-dependant",
        ),
    ],
)
def test_the_inherits_order(
    types: dict[str, dict[str, Any]],
    order: list[str],
    parents: dict[str, str],
    findings: list[str],
) -> None:
    """Parents resolve before their children, whatever the order the types are given
    in; every member of a cycle, and every unknown parent, is reported, and the type
    whose ``inherits`` is ignored stays a root."""
    assert _inherits_order(types) == (order, parents, findings)


INHERITS_INDEX = """\
.. a:: A
   :id: A_001

.. b:: B
   :id: B_001

.. e:: E
   :id: E_001

.. f:: F
   :id: F_001
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                {
                    "a": {
                        "title": "A",
                        "prefix": "A_",
                        "inherits": "b",
                        "fields": {"x": {"nullable": False, "default": "a"}},
                    },
                    "b": {"title": "B", "prefix": "B_", "inherits": "a"},
                    "e": {"title": "E", "prefix": "E_", "inherits": "nope"},
                    "f": {
                        "title": "F",
                        "prefix": "F_",
                        "inherits": "e",
                        "fields": {"x": {"default": "f"}},
                    },
                    # a type the GitHub service adds once the configuration is read
                    "g": {"title": "G", "prefix": "G_", "inherits": "issue"},
                },
                {"x": {"nullable": True}},
            ),
            INHERITS_INDEX,
        )
    ],
    indirect=True,
)
def test_an_inherits_that_cannot_be_used_is_reported(test_app: Any) -> None:
    """A cycle and an unknown parent are each reported, and the build goes on: each
    type stays, a root, its own declarations applied; a parent is any need type the
    schema knows, one a service adds included."""
    app = test_app
    app.build()
    # the unknown parents first, then the cycles
    assert build_warnings(app) == [
        "WARNING: Need type 'e' inherits 'nope', which is not a need type; its "
        "inherits is ignored. [needs.type_inherits]",
        "WARNING: Need type 'a' inherits 'b' on a cycle (a -> b -> a); its inherits "
        "is ignored. [needs.type_inherits]",
        "WARNING: Need type 'b' inherits 'a' on a cycle (a -> b -> a); its inherits "
        "is ignored. [needs.type_inherits]",
    ]
    assert {k: v["x"] for k, v in _needs(app).items()} == {
        "A_001": "a",
        "B_001": None,
        "E_001": None,
        "F_001": "f",
    }
    assert _field(app, "a", "x").nullable is False
    assert _field(app, "b", "x") is _field(app, None, "x")


# -- each key, on a field, a link type, a core field and a derived field ------------------

#: a field with an enum, nullable
X = {"nullable": True, "schema": {"type": "string", "enum": ["A", "B", "C"]}}
#: a link type
BLOCKS = {"incoming": "is blocked by", "outgoing": "blocks"}
#: a field derived on ``req``: a ``req`` copies its title, any other type holds "D"
DERIVED = {
    "schema": {"type": "string"},
    "nullable": True,
    "default": "D",
    "derive_by_type": {"req": {"kind": "copy", "field": "title"}},
}


def _declared(
    case_id: str,
    declarations: dict[str, Any],
    warnings: list[str],
    *,
    fields: dict[str, Any] | None = None,
    links: dict[str, Any] | None = None,
) -> Any:
    return pytest.param(
        _project(_conf(_types(spec=declarations), fields, links)),
        [
            f"WARNING: {text} [needs.{code}]"
            for code, text in (w.split(" ", 1) for w in warnings)
        ],
        id=case_id,
    )


def test_a_project_without_declarations_registers_none(
    make_app: Any, tmp_path: Path
) -> None:
    """Without a per-type entry every type reads the global view."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "conf.py").write_text(
        _conf(_types(), {"x": X}, {"blocks": BLOCKS}), encoding="utf-8"
    )
    (tmp_path / "src" / "index.rst").write_text("Case\n====\n", encoding="utf-8")
    app = make_app("needs", srcdir=tmp_path / "src")
    app.build()
    schema = _schema(app)
    assert not any(
        schema.type_declarations(field.name) for field in schema.iter_all_fields()
    )
    assert schema.for_type("spec") is schema.for_type(None)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={
                        "fields": {
                            "x": {
                                "description": "The x of a spec",
                                "schema": {"enum": ["A", "B"]},
                                "nullable": False,
                                "default": "A",
                                "predicates": [["id == 'S_002'", "B"]],
                            },
                            "status": {
                                "schema": {"enum": ["open", "closed"]},
                                "default": "open",
                            },
                        },
                        "links": {
                            "blocks": {
                                "description": "What a spec blocks",
                                "schema": {"maxItems": 1},
                                "default": ["R_001"],
                                "predicates": [["id == 'S_002'", ["R_002"]]],
                            }
                        },
                    }
                ),
                {"x": X},
                {"blocks": BLOCKS},
            ),
            ".. req:: A\n   :id: R_001\n\n.. req:: B\n   :id: R_002\n\n"
            ".. spec:: C\n   :id: S_001\n\n.. spec:: D\n   :id: S_002\n",
        )
    ],
    indirect=True,
)
def test_every_key_on_a_field_a_link_type_and_a_core_field(test_app: Any) -> None:
    """Each key of a ``fields`` and a ``links`` entry declares the field anew for the
    needs of the type; a core field takes a default and a narrower enum too. The
    needs of every other type read the global declarations."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    x = _field(app, "spec", "x")
    assert (x.description, x.schema, x.nullable, x.default, x.predicate_defaults) == (
        "The x of a spec",
        {"type": "string", "enum": ["A", "B"]},
        False,
        FieldLiteralValue("A"),
        (("id == 'S_002'", FieldLiteralValue("B")),),
    )
    status = _field(app, "spec", "status")
    assert (status.schema["enum"], status.default) == (
        ["open", "closed"],
        FieldLiteralValue("open"),
    )
    blocks = _field(app, "spec", "blocks")
    assert (blocks.description, blocks.schema, blocks.default) == (
        "What a spec blocks",
        {"type": "array", "items": {"type": "string"}, "maxItems": 1},
        LinksLiteralValue([NeedLink(id="R_001")]),
    )
    assert blocks.predicate_defaults == (
        ("id == 'S_002'", LinksLiteralValue([NeedLink(id="R_002")])),
    )
    for name in ("x", "status", "blocks"):
        assert _field(app, "req", name) is _schema(app).global_declaration(name)
    assert {k: (v["x"], v["status"], v["blocks"]) for k, v in _needs(app).items()} == {
        "R_001": (None, None, []),
        "R_002": (None, None, []),
        "S_001": ("A", "open", ["R_001"]),
        "S_002": ("B", "open", ["R_002"]),
    }


CONFLICTS = [
    _declared(
        "not-a-field",
        {"fields": {"nope": {"description": "d"}}},
        [
            "type_conflict needs_types['spec'].fields['nope'] declares 'nope', which "
            "is not a field; the entry is ignored"
        ],
    ),
    _declared(
        "a-link-type-in-fields",
        {"fields": {"blocks": {"description": "d"}}},
        [
            "type_conflict needs_types['spec'].fields['blocks'] declares 'blocks', "
            "which is a link type, not a field; the entry is ignored"
        ],
        links={"blocks": BLOCKS},
    ),
    _declared(
        "not-a-link-type",
        {"links": {"nope": {"description": "d"}}},
        [
            "type_conflict needs_types['spec'].links['nope'] declares 'nope', which "
            "is not a link type; the entry is ignored"
        ],
    ),
    _declared(
        "a-field-in-links",
        {"links": {"x": {"description": "d"}}},
        [
            "type_conflict needs_types['spec'].links['x'] declares 'x', which is a "
            "field, not a link type; the entry is ignored"
        ],
        fields={"x": X},
    ),
    _declared(
        "a-default-of-title",
        {"fields": {"title": {"default": "T"}}},
        [
            "type_conflict needs_types['spec'].fields['title'] sets a 'default' that "
            "cannot be used: Defaults are not allowed for this field; the entry is "
            "ignored"
        ],
    ),
    _declared(
        "a-default-that-does-not-convert",
        {"fields": {"y": {"description": "kept?", "default": 5}}},
        [
            "type_conflict needs_types['spec'].fields['y'] sets a 'default' that "
            "cannot be used: Invalid value for field 'y': 5; the entry is ignored"
        ],
        fields={"y": {"nullable": True}},
    ),
    _declared(
        "predicates-that-do-not-convert",
        {"fields": {"y": {"predicates": [["id == 'S_001'", 5]]}}},
        [
            "type_conflict needs_types['spec'].fields['y'] sets 'predicates' that "
            "cannot be used: Invalid value for field 'y': 5; the entry is ignored"
        ],
        fields={"y": {"nullable": True}},
    ),
    _declared(
        "a-schema-that-is-not-valid",
        {"fields": {"y": {"schema": {"minLength": "one"}}}},
        [
            "type_conflict needs_types['spec'].fields['y'] cannot be declared: "
            'Invalid schema: "one" is not of type "integer"; the entry is ignored'
        ],
        fields={"y": {"nullable": True}},
    ),
    _declared(
        "a-default-of-a-derived-field",
        {"fields": {"dy": {"default": "S"}}},
        [
            "type_conflict needs_types['spec'].fields['dy'] sets 'default', but 'dy' "
            "is derived (by need type): a need type declares only its description, "
            "schema and nullable; the entry is ignored"
        ],
        fields={"dy": DERIVED},
    ),
    _declared(
        "a-default-and-predicates-of-a-derived-field",
        {"fields": {"dy": {"default": "S", "predicates": [["True", "P"]]}}},
        [
            "type_conflict needs_types['spec'].fields['dy'] sets 'default' and "
            "'predicates', but 'dy' is derived (by need type): a need type declares "
            "only its description, schema and nullable; the entry is ignored"
        ],
        fields={"dy": DERIVED},
    ),
    _declared(
        "an-enum-on-a-derived-field",
        {"fields": {"dy": {"schema": {"enum": ["D", "E"]}}}},
        [
            "type_conflict needs_types['spec'].fields['dy'] adds an 'enum', but 'dy' "
            "is derived (by need type) and its rules are checked against its "
            "declaration, which has none; the entry is ignored"
        ],
        fields={"dy": DERIVED},
    ),
    _declared(
        "a-default-of-a-derived-link-type",
        {"links": {"dl": {"default": ["R_001"]}}},
        [
            "type_conflict needs_types['spec'].links['dl'] sets 'default', but 'dl' "
            "is derived (by need type): a need type declares only its description "
            "and schema; the entry is ignored"
        ],
        links={
            "dl": {
                **BLOCKS,
                "derive_by_type": {"req": {"kind": "links", "where": "id == 'R_001'"}},
            }
        },
    ),
    _declared(
        "another-type",
        {"fields": {"x": {"schema": {"type": "integer"}}}},
        [
            "type_conflict needs_types['spec'].fields['x'] cannot be declared with "
            "type 'integer' (items None): its type is 'string' (items None) on every "
            "need type; the entry is ignored"
        ],
        fields={"x": X},
    ),
    # A-6: None is no value of a field that is not nullable
    _declared(
        "a-default-none-not-nullable",
        {"fields": {"n": {"default": None}}},
        [
            "type_conflict needs_types['spec'].fields['n'] sets a 'default' that "
            "cannot be used: Invalid value for field 'n': None; the entry is ignored"
        ],
        fields={"n": {"nullable": False, "default": "n"}},
    ),
]


@pytest.mark.parametrize(("test_app", "warnings"), CONFLICTS, indirect=["test_app"])
def test_an_entry_that_cannot_be_applied(test_app: Any, warnings: list[str]) -> None:
    """An entry naming no field or link type of its table, or setting what the field
    does not take, is one ``needs.type_conflict`` warning: the whole entry is ignored,
    and the type reads the global declaration."""
    app = test_app
    app.build()
    assert build_warnings(app) == warnings
    assert not any(
        _schema(app).type_declarations(field.name)
        for field in _schema(app).iter_all_fields()
    )


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={
                        "fields": {
                            "dx": {
                                "description": "A spec's dx",
                                "schema": {"maxLength": 9},
                                "nullable": False,
                            },
                            "de": {"schema": {"enum": ["D"]}},
                        }
                    }
                ),
                {
                    "dx": DERIVED,
                    "de": {
                        **DERIVED,
                        "schema": {"type": "string", "enum": ["A", "D"]},
                    },
                },
            ),
            ".. req:: A\n   :id: R_001\n\n.. spec:: B\n   :id: S_001\n",
        )
    ],
    indirect=True,
)
def test_a_derived_field_takes_a_description_a_schema_and_nullable(
    test_app: Any,
) -> None:
    """On a derived field a type declares its description, a narrower schema (an enum
    only where the field has one) and ``nullable``."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    dx = _field(app, "spec", "dx")
    assert (dx.description, dx.schema, dx.nullable) == (
        "A spec's dx",
        {"type": "string", "maxLength": 9},
        False,
    )
    assert _field(app, "spec", "de").schema == {"type": "string", "enum": ["D"]}


WIDENINGS = [
    _declared(
        "a-min-items-on-a-link-type-without-a-default",
        {"links": {"blocks": {"schema": {"minItems": 1}}}},
        [
            "type_widening needs_types['spec'].links['blocks'] widens the field: "
            "Default [] is not valid against the narrowed schema: [] has less than 1 "
            "item."
        ],
        links={"blocks": BLOCKS},
    ),
    _declared(
        "an-enum-superset",
        {"fields": {"x": {"schema": {"enum": ["A", "B", "C", "D"]}}}},
        [
            "type_widening needs_types['spec'].fields['x'] widens the field: Child "
            "'enum' values ['A', 'B', 'C', 'D'] are not a subset of parent 'enum' "
            "values ['A', 'B', 'C']."
        ],
        fields={"x": X},
    ),
    _declared(
        "a-lower-minimum-and-a-higher-maximum",
        {"fields": {"s": {"schema": {"minimum": -1, "maximum": 11}}}},
        [
            "type_widening needs_types['spec'].fields['s'] widens the field: Child "
            "'minimum' -1 is less than parent 'minimum' 0.",
            "type_widening needs_types['spec'].fields['s'] widens the field: Child "
            "'maximum' 11 is greater than parent 'maximum' 10.",
        ],
        fields={
            "s": {
                "nullable": True,
                "schema": {"type": "integer", "minimum": 0, "maximum": 10},
            }
        },
    ),
    _declared(
        "nullable-false-to-true",
        {"fields": {"n": {"nullable": True}}},
        [
            "type_widening needs_types['spec'].fields['n'] widens the field: Cannot "
            "change 'nullable' from False to True in child."
        ],
        fields={"n": {"nullable": False, "default": "n"}},
    ),
    _declared(
        "an-enum-below-the-default",
        {"fields": {"q": {"schema": {"enum": ["A", "B"]}}}},
        [
            "type_widening needs_types['spec'].fields['q'] widens the field: Default "
            '\'QM\' is not valid against the narrowed schema: "QM" is not one of "A" '
            'or "B".'
        ],
        fields={
            "q": {
                "nullable": True,
                "schema": {"type": "string", "enum": ["A", "B", "QM"]},
                "default": "QM",
            }
        },
    ),
]


@pytest.mark.parametrize(("test_app", "warnings"), WIDENINGS, indirect=["test_app"])
def test_an_entry_that_widens_the_field(test_app: Any, warnings: list[str]) -> None:
    """An entry that is not a narrowing of the field is one ``needs.type_widening``
    warning per reason; the type keeps the global declaration."""
    app = test_app
    app.build()
    assert build_warnings(app) == warnings
    assert not any(
        _schema(app).type_declarations(field.name)
        for field in _schema(app).iter_all_fields()
    )


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={
                        "fields": {
                            "q": {"schema": {"enum": ["A", "B"]}, "default": "A"}
                        }
                    }
                ),
                {
                    "q": {
                        "nullable": True,
                        "schema": {"type": "string", "enum": ["A", "B", "QM"]},
                        "default": "QM",
                    }
                },
            ),
            ".. req:: A\n   :id: R_001\n\n.. spec:: B\n   :id: S_001\n",
        )
    ],
    indirect=True,
)
def test_an_enum_below_the_default_with_a_default_inside(test_app: Any) -> None:
    """An enum that leaves out the field's default is a narrowing once the entry sets
    a default inside it."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert {k: v["q"] for k, v in _needs(app).items()} == {"R_001": "QM", "S_001": "A"}


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={
                        "fields": {
                            "q": {"schema": {"enum": ["A", "B"]}, "default": None}
                        }
                    }
                ),
                {
                    "q": {
                        "nullable": True,
                        "schema": {"type": "string", "enum": ["A", "B", "QM"]},
                        "default": "QM",
                    }
                },
            ),
            ".. req:: A\n   :id: R_001\n\n.. spec:: B\n   :id: S_001\n",
        )
    ],
    indirect=True,
)
def test_a_default_of_none_on_a_nullable_field_is_no_default(test_app: Any) -> None:
    """``default = None`` (in ``conf.py``) on a nullable field gives the type no
    default: its needs leave the field unset, and an enum may then leave out the
    field's default."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _field(app, "spec", "q").default is None
    assert {k: v["q"] for k, v in _needs(app).items()} == {"R_001": "QM", "S_001": None}


# -- inherits: what a child declares -------------------------------------------------------

CHAIN_INDEX = """\
.. req:: A
   :id: R_001

.. spec:: B
   :id: S_001

.. impl:: C
   :id: I_001

.. test:: D
   :id: T_001
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                {
                    # each child before its parent: parents resolve first
                    "impl": {
                        "title": "Implementation",
                        "prefix": "I_",
                        "inherits": "spec",
                    },
                    "test": {"title": "Test Case", "prefix": "T_", "inherits": "req"},
                    "spec": {
                        "title": "Specification",
                        "prefix": "S_",
                        "inherits": "req",
                        "fields": {"x": {"nullable": False, "default": "B"}},
                    },
                    "req": {
                        "title": "Requirement",
                        "prefix": "R_",
                        "fields": {"x": {"schema": {"enum": ["A", "B"]}}},
                    },
                },
                {"x": X},
            ),
            CHAIN_INDEX,
        )
    ],
    indirect=True,
)
def test_a_child_narrows_what_its_parent_declares(test_app: Any) -> None:
    """A type with no entry of its own on a field reads its parent's declaration; a
    child narrows it further, and a grandchild reads the child's -- in whatever order
    the types are given."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    req, spec, impl, test = (
        _field(app, t, "x") for t in ("req", "spec", "impl", "test")
    )
    assert (req.schema["enum"], req.nullable, req.default) == (["A", "B"], True, None)
    assert (spec.schema["enum"], spec.nullable, spec.default) == (
        ["A", "B"],
        False,
        FieldLiteralValue("B"),
    )
    assert impl is spec
    assert test is req
    assert list(_schema(app).type_declarations("x")) == ["req", "spec", "impl", "test"]
    assert {k: v["x"] for k, v in _needs(app).items()} == {
        "R_001": None,
        "S_001": "B",
        "I_001": "B",
        "T_001": None,
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    req={"fields": {"x": {"schema": {"enum": ["A", "B"]}}}},
                    spec={
                        "inherits": "req",
                        "fields": {
                            "x": {
                                "description": "wider",
                                "schema": {"enum": ["A", "B", "C"]},
                            }
                        },
                    },
                    impl={
                        "inherits": "spec",
                        "fields": {"x": {"schema": {"enum": ["A", "B", "C"]}}},
                    },
                ),
                {"x": X},
            )
        )
    ],
    indirect=True,
)
def test_a_child_widening_its_parent_is_refused(test_app: Any) -> None:
    """A child's entry is a narrowing of its parent's declaration, not only of the
    field's: one that widens the parent's is refused, naming the type whose entry made
    the declaration (a grandparent, where the parent's own entry was refused), and the
    child reads its parent's declaration."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['spec'].fields['x'] widens the field as need type 'req' "
        "declares it: Child 'enum' values ['A', 'B', 'C'] are not a subset of parent "
        "'enum' values ['A', 'B']. [needs.type_widening]",
        "WARNING: needs_types['impl'].fields['x'] widens the field as need type 'req' "
        "declares it: Child 'enum' values ['A', 'B', 'C'] are not a subset of parent "
        "'enum' values ['A', 'B']. [needs.type_widening]",
    ]
    assert _field(app, "spec", "x") is _field(app, "req", "x")
    assert _field(app, "impl", "x") is _field(app, "req", "x")


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    req={"fields": {"x": {"schema": {"enum": ["A", "B", "C"]}}}},
                    spec={
                        "inherits": "req",
                        "fields": {"x": {"schema": {"enum": ["A", "B"]}}},
                    },
                    impl={
                        "inherits": "spec",
                        "fields": {"x": {"schema": {"enum": ["A", "B", "C"]}}},
                    },
                ),
                {
                    "x": {
                        **X,
                        "schema": {"type": "string", "enum": ["A", "B", "C", "D"]},
                    }
                },
            )
        )
    ],
    indirect=True,
)
def test_a_widening_names_the_nearest_declaring_type(test_app: Any) -> None:
    """A widening names the nearest type whose entry made the declaration it widens:
    the parent whose own entry narrowed it, not the root of the chain."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['impl'].fields['x'] widens the field as need type "
        "'spec' declares it: Child 'enum' values ['A', 'B', 'C'] are not a subset of "
        "parent 'enum' values ['A', 'B']. [needs.type_widening]",
    ]
    assert _field(app, "impl", "x") is _field(app, "spec", "x")
    assert _field(app, "spec", "x").schema["enum"] == ["A", "B"]


# -- the value of a need ---------------------------------------------------------------------

PRECEDENCE_INDEX = """\
.. req:: A
   :id: R_001

.. spec:: B
   :id: S_001

.. spec:: C
   :id: S_002

.. spec:: D
   :id: S_003
   :x: authored

.. impl:: P
   :id: I_001

.. impl:: Q
   :id: I_002
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={"fields": {"x": {"default": "type"}, "n": {"default": "3"}}},
                    impl={"fields": {"x": {"predicates": [["title == 'Q'", "impl"]]}}},
                ),
                {
                    "x": {
                        "nullable": True,
                        "default": "global",
                        "predicates": [
                            ["id == 'S_002'", "predicate"],
                            ["title == 'P'", "predicate"],
                        ],
                    },
                    "n": {"nullable": True, "schema": {"type": "integer"}},
                },
            ),
            PRECEDENCE_INDEX,
        ),
        _toml_project(
            """\
[needs]
build_json = true

[needs.fields.x]
nullable = true
default = "global"
predicates = [["id == 'S_002'", "predicate"], ["title == 'P'", "predicate"]]

[needs.fields.n]
nullable = true
schema = { type = "integer" }

[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.spec]
title = "Specification"
prefix = "S_"

[needs.types.spec.fields.x]
default = "type"

[needs.types.spec.fields.n]
default = "3"

[needs.types.impl]
title = "Implementation"
prefix = "I_"

[needs.types.impl.fields.x]
predicates = [["title == 'Q'", "impl"]]
""",
            PRECEDENCE_INDEX,
        ),
    ],
    indirect=True,
)
def test_what_a_need_of_the_type_holds(test_app: Any) -> None:
    """A value given in the need wins; else the predicates of the type's declaration
    -- the field's, unless the type declares its own, which replace them --; else the
    type's default; the needs of every other type take the field's default. A value
    in the configuration is converted to the field's type, as ``needs_fields`` does."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert {k: (v["x"], v["n"]) for k, v in _needs(app).items()} == {
        "R_001": ("global", None),
        "S_001": ("type", 3),
        "S_002": ("predicate", 3),
        "S_003": ("authored", 3),
        "I_001": ("global", None),
        "I_002": ("impl", None),
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _toml_project(
            """\
[needs]
build_json = true

[needs.fields.x]
nullable = true

[[needs.types]]
directive = "req"
title = "Requirement"
prefix = "R_"

[[needs.types]]
directive = "spec"
title = "Specification"
prefix = "S_"

[needs.types.fields.x]
default = "last"
""",
            ".. req:: A\n   :id: R_001\n\n.. spec:: B\n   :id: S_001\n",
        )
    ],
    indirect=True,
)
def test_a_toml_sub_table_attaches_to_the_last_array_element(test_app: Any) -> None:
    """In the list shape, ``[needs.types.fields.x]`` after the ``[[needs.types]]``
    tables belongs to the last of them (TOML's rule)."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert {k: v["x"] for k, v in _needs(app).items()} == {
        "R_001": None,
        "S_001": "last",
    }


#: a ``config-inited`` handler after the normaliser (priority 12) appending an entry
#: to ``needs_types`` as it is, not through ``add_need_type``
APPENDING_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {{"x": {{"nullable": True}}}}


def _append(app, config):
    config.needs_types.append({entry!r})


def setup(app):
    app.connect("config-inited", _append, priority=500)
"""

EXT = {"directive": "ext", "title": "Extension", "prefix": "E_"}


@pytest.mark.parametrize(
    ("test_app", "warning"),
    [
        pytest.param(
            _project(APPENDING_CONF.format(entry={**EXT, "fields": ["x"]})),
            "needs_types['ext'] has a 'fields' that is not a mapping (got list); the "
            "key is ignored",
            id="fields-a-list",
        ),
        pytest.param(
            _project(APPENDING_CONF.format(entry={**EXT, "inherits": ["req"]})),
            "needs_types['ext'] has an 'inherits' that is not a non-empty string (got "
            "list); the key is ignored",
            id="inherits-a-list",
        ),
        pytest.param(
            _project(APPENDING_CONF.format(entry={**EXT, "fields": {"x": "abc"}})),
            "needs_types['ext'].fields['x'] is not a mapping (got str); the entry is "
            "ignored",
            id="a-declaration-a-string",
        ),
        pytest.param(
            _project(
                APPENDING_CONF.format(
                    entry={**EXT, "fields": {"x": {"schema": ["string"]}}}
                )
            ),
            "needs_types['ext'].fields['x'] has a 'schema' that is not a mapping (got "
            "list); the key is ignored",
            id="a-schema-a-list",
        ),
    ],
    indirect=["test_app"],
)
def test_an_entry_appended_after_the_configuration_is_resolved(
    test_app: Any, warning: str
) -> None:
    """An entry an extension appends to ``needs_types`` once the configuration is
    resolved has its ``inherits``, ``fields`` and ``links`` checked where they are
    read: what is not of its shape is reported as the configuration's own finding and
    ignored, and the build goes on."""
    app = test_app
    app.build()
    assert build_warnings(app) == [f"WARNING: {warning} [needs.config]"]
    assert _field(app, "ext", "x") == _field(app, None, "x")


# -- what reads the declarations -------------------------------------------------------------

DELETE_INDEX = """\
.. req:: A
   :id: R_001
   :x: a
   :y: 1
   :w: a

.. spec:: B
   :id: S_001
   :x: b
   :y: 2
   :w: b

.. req:: C
   :id: R_002
   :x: [[copy("title")]]

.. spec:: D
   :id: S_002
   :x: [[copy("title")]]

.. needextend:: type in ["req", "spec"]
   :-x:
   :-y:
   :-w:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={
                        "fields": {
                            "x": {"nullable": False, "default": "dx"},
                            "y": {"nullable": False, "default": 7},
                            "w": {"nullable": False, "default": ["dw"]},
                        }
                    }
                ),
                {
                    "x": {"nullable": True},
                    "y": {"nullable": True, "schema": {"type": "integer"}},
                    "w": {
                        "nullable": True,
                        "schema": {"type": "array", "items": {"type": "string"}},
                    },
                },
            ),
            DELETE_INDEX,
        )
    ],
    indirect=True,
)
def test_a_needextend_deletes_to_the_empty_value_of_the_type(test_app: Any) -> None:
    """``:-x:`` empties a field to what the need's type declares: ``None`` where the
    field is nullable on it, else the empty value of the field's type; a dynamic
    function the need gave the field is deleted with it."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert {k: (v["x"], v["y"], v["w"]) for k, v in _needs(app).items()} == {
        "R_001": (None, None, None),
        "S_001": ("", 0, []),
        "R_002": (None, None, None),
        "S_002": ("", 0, []),
    }


GONE_CONF = """\
import os

extensions = ["sphinx_needs"]
needs_build_json = True


def setup(app):
    if os.environ.get("PTYPE_WITH_GONE"):
        from sphinx_needs.api import add_field

        add_field("gone", "a field an extension registers", nullable=True)
"""

GONE_INDEX = """\
Case
====

.. req:: A
   :id: R_001
   :gone: kept

.. needextend:: R_001
   :-gone:
"""


def test_a_deleted_field_the_schema_no_longer_has(
    make_app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A needextend kept from an earlier build may delete a field the schema of this
    build no longer has (an extension's, no longer registered): the deletion is not
    applied -- the need keeps the value it was written with, which a delete would have
    emptied -- and the build goes on."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(GONE_CONF, encoding="utf-8")
    (srcdir / "index.rst").write_text(GONE_INDEX, encoding="utf-8")
    monkeypatch.setenv("PTYPE_WITH_GONE", "1")
    app = make_app("needs", srcdir=srcdir)
    app.build()
    assert build_warnings(app) == []
    assert _needs(app)["R_001"]["gone"] is None
    # the next application registers its own nodes and directives
    app.cleanup()
    monkeypatch.delenv("PTYPE_WITH_GONE")
    # the same source and build directories: the extend comes from the environment
    app = make_app("needs", srcdir=srcdir)
    app.build()
    assert build_warnings(app) == []
    # the need as written in the first build keeps its value: nothing deleted it
    assert _needs(app)["R_001"]["gone"] == "kept"


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(_types(spec={"fields": {"template": {"default": "tpl"}}})),
        )
    ],
    indirect=True,
)
def test_a_template_default_of_one_type_is_a_declared_default(test_app: Any) -> None:
    """A type's default of ``template`` is a default the field may be given."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    schema = _schema(app)
    assert schema.global_declaration("template").default is None
    assert schema.declares_default("template")


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(spec={"fields": {"score": {"description": "A spec's score"}}}),
                {
                    "score": {
                        "schema": {"type": "string"},
                        "nullable": True,
                        "derive": {"kind": "copy", "field": "nope"},
                    }
                },
            ),
            ".. spec:: B\n   :id: S_001\n",
        )
    ],
    indirect=True,
)
def test_a_declaration_of_a_field_whose_derive_cannot_be_read(test_app: Any) -> None:
    """A field whose ``derive`` cannot be read is reported as such, and a type still
    declares it anew: the build goes on."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == 1
    assert warnings[0].endswith("[needs.derive_invalid]")
    assert _field(app, "spec", "score").description == "A spec's score"
    assert _needs(app)["S_001"]["score"] is None
