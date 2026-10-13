"""Declared derived fields per need type: ``derive_by_type``.

Beside ``derive``, or instead of it, a field or link type may carry ``derive_by_type``:
a table of need type (the directive name) to rule, each read as ``derive`` is, and
overriding ``derive`` on that type. A need of a type without a rule holds the field's
literal ``default`` (in the field's type), else ``None`` when it is nullable, else the
empty value of its type. The field is derived on every need type: closed to authors and
needextend everywhere, ``readOnly`` in the export, never in a fingerprint.

The corpus (``fixtures/derive_conformance.toml``, the ``by-type-*`` cases) pins the values
both tools compute; the tests here pin the rest: the texts and order of the findings, the
reading of the tables, the off-type value against the field's schema, the legacy and API
spellings, and the per-type load-time cycles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.derive import (
    DeriveInvalid,
    DeriveRule,
    check_derive_rules,
    fingerprint_names,
    parse_derive_by_type,
)
from sphinx_needs.needs_schema import (
    FieldLiteralValue,
    FieldSchema,
    FieldsSchema,
    LinkDisplayConfig,
    LinkSchema,
    LinksLiteralValue,
)
from sphinx_needs_testkit import build_warnings

#: the default need types, each with its title
NEED_TYPES = {
    "req": "Requirement",
    "spec": "Specification",
    "impl": "Implementation",
    "test": "Test Case",
}

TOML_CONF = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
"""

_CLOSED = "the field cannot be set in a need or by a needextend"


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _export_schema(app: Any) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs_schema"]["properties"]


def _warnings(app: Any) -> list[str]:
    """The build's warnings, but for the deprecation of the legacy options."""
    return [w for w in build_warnings(app) if not w.endswith("[needs.deprecated]")]


def _project(conf: str, index: str, **files: str) -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Case\n====\n\n" + index),
            *((Path(name), text) for name, text in files.items()),
        ],
    }


def _toml_project(config: str, index: str, **files: str) -> dict[str, Any]:
    return _project(TOML_CONF, index, **{"ubproject.toml": config, **files})


def _field(name: str = "f", **kwargs: Any) -> FieldSchema:
    return FieldSchema(
        name=name, schema=kwargs.pop("schema", {"type": "number"}), **kwargs
    )


SUM = DeriveRule(kind="sum", field="hours", over="links")
COPY = DeriveRule(kind="copy", field="hours")


# -- reading the table -----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,rules,problems",
    [
        pytest.param(
            {"req": {"kind": "sum", "field": "hours", "over": "links"}},
            {"req": SUM},
            [],
            id="one-entry",
        ),
        pytest.param(
            {"spec": {"kind": "copy", "field": "hours"}, "epic": {"kind": "copy"}},
            {"spec": COPY},
            [
                (
                    "derive_by_type.epic",
                    "'epic' is not a need type; the entry is ignored",
                )
            ],
            id="unknown-type-ignored",
        ),
        pytest.param(
            {"Requirement": {"kind": "copy", "field": "hours"}},
            {},
            [
                (
                    "derive_by_type.Requirement",
                    "'Requirement' is not a need type (did you mean 'req'?); "
                    "the entry is ignored",
                )
            ],
            id="a-title-is-not-a-type",
        ),
        pytest.param(
            {"REQ": {"kind": "copy", "field": "hours"}},
            {},
            [("derive_by_type.REQ", "'REQ' is not a need type; the entry is ignored")],
            id="case-sensitive",
        ),
        pytest.param(
            [1, 2],
            {},
            [("derive_by_type", "it is not a table of need types")],
            id="not-a-table",
        ),
        pytest.param(
            {}, {}, [("derive_by_type", "it names no need type")], id="empty-table"
        ),
        pytest.param(
            {"req": 3},
            {"req": DeriveInvalid(None, "it is not a table naming a 'kind'")},
            [("derive_by_type.req", "it is not a table naming a 'kind'")],
            id="entry-not-a-table",
        ),
        pytest.param(
            {"req": {"kind": "copy", "field": "x", "types": ["req"]}},
            {
                "req": DeriveInvalid(
                    "copy",
                    "kind 'copy': 'types' is not a role; a rule for some need types "
                    "is declared under derive_by_type",
                )
            },
            [
                (
                    "derive_by_type.req",
                    "kind 'copy': 'types' is not a role; a rule for some need types "
                    "is declared under derive_by_type",
                )
            ],
            id="entry-invalid",
        ),
        pytest.param(
            {1: {"kind": "copy", "field": "hours"}},
            {},
            [("derive_by_type.1", "'1' is not a need type; the entry is ignored")],
            id="key-not-a-string",
        ),
    ],
)
def test_parse_derive_by_type(raw: Any, rules: dict, problems: list) -> None:
    """Each entry is read as ``derive`` is; a key must be a declared need type's
    DIRECTIVE name, case-sensitive (a title is named in a hint); a table that cannot be
    read gives no rule on any type."""
    assert parse_derive_by_type(raw, on_link=False, need_types=NEED_TYPES) == (
        rules,
        problems,
    )


def test_parse_derive_by_type_on_a_link_type() -> None:
    """On a link type an entry must compute a link list, as ``derive`` must."""
    rules, problems = parse_derive_by_type(
        {"req": {"kind": "copy", "field": "hours"}},
        on_link=True,
        need_types=NEED_TYPES,
    )
    assert isinstance(rules["req"], DeriveInvalid)
    assert problems == [
        (
            "derive_by_type.req",
            "kind 'copy' computes a value, so it is declared on a field (needs_fields), "
            "not on a link type",
        )
    ]


# -- the schema ------------------------------------------------------------------------


def test_the_rule_of_a_need_type() -> None:
    """A type's own entry, else ``derive``, else none (off-type)."""
    both = _field(derive=SUM, derive_by_type={"spec": COPY})
    assert (both.rule_for("spec"), both.rule_for("req")) == (COPY, SUM)
    alone = _field(derive_by_type={"spec": COPY})
    assert (alone.rule_for("spec"), alone.rule_for("req")) == (COPY, None)
    assert alone.derived and both.derived
    assert not _field().derived
    # an empty table: derived, with no rule on any type
    nowhere = _field(derive_by_type={})
    assert nowhere.derived and nowhere.rule_for("req") is None


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        pytest.param(
            {"default": FieldLiteralValue(0), "nullable": True}, 0.0, id="default-float"
        ),
        pytest.param(
            {
                "schema": {"type": "array", "items": {"type": "number"}},
                "default": FieldLiteralValue([1, 2.5]),
            },
            [1.0, 2.5],
            id="default-array-of-numbers",
        ),
        pytest.param(
            {"schema": {"type": "integer"}, "default": FieldLiteralValue(3)},
            3,
            id="default-integer",
        ),
        pytest.param({"nullable": True}, None, id="nullable"),
        pytest.param({"nullable": False}, 0.0, id="typed-empty-number"),
        pytest.param(
            {"schema": {"type": "string"}, "nullable": False}, "", id="typed-empty-str"
        ),
    ],
)
def test_the_off_type_value(kwargs: dict[str, Any], expected: Any) -> None:
    """The literal default in the field's type, else ``None``, else the typed empty."""
    value = _field(derive_by_type={"req": COPY}, **kwargs).off_type_value()
    assert value == expected and type(value) is type(expected)


def test_only_derive_by_type_alone_takes_a_default() -> None:
    """A derived field takes no default, but for the off-type value of
    ``derive_by_type`` alone; with ``derive`` beside it every type has a rule."""
    _field(derive_by_type={"req": COPY}, default=FieldLiteralValue(1))
    with pytest.raises(ValueError, match="Defaults are not allowed"):
        _field(derive=SUM, derive_by_type={"req": COPY}, default=FieldLiteralValue(1))
    with pytest.raises(ValueError, match="derive_by_type must map need types"):
        _field(derive_by_type={"req": {"kind": "copy"}})


def test_the_off_type_links() -> None:
    link = LinkSchema(
        name="rel",
        schema={"type": "array", "items": {"type": "string"}},
        display=LinkDisplayConfig(incoming="in", outgoing="out"),
        default=LinksLiteralValue([]),
        derive_by_type={"req": DeriveRule(kind="links", where="type == 'spec'")},
    )
    assert link.derived and link.rule_for("spec") is None
    assert link.off_type_value() == []


def _cycle_schema(
    *,
    cyc_b_derive: DeriveRule | None = None,
    cyc_b: dict[str, DeriveRule] | None = None,
) -> FieldsSchema:
    """``cyc_a`` copies ``cyc_b`` on every type; ``cyc_b`` carries the given rules."""
    schema = FieldsSchema()
    schema.add_extra_field(
        _field(
            "cyc_a",
            schema={"type": "string"},
            derive=DeriveRule(kind="copy", field="cyc_b"),
        )
    )
    schema.add_extra_field(
        _field(
            "cyc_b",
            schema={"type": "string"},
            derive=cyc_b_derive,
            derive_by_type=cyc_b,
        )
    )
    return schema


def test_a_load_time_cycle_is_per_need_type() -> None:
    """``cyc_a``'s ``derive`` reads ``cyc_b``, whose ``req`` entry reads ``cyc_a`` back:
    the entry cannot be read, and ``derive`` cannot be read on ``req`` only."""
    schema = _cycle_schema(cyc_b={"req": DeriveRule(kind="copy", field="cyc_a")})
    problems = check_derive_rules(schema, need_types=NEED_TYPES)
    assert [(p.name, p.part, p.on_types) for p in problems] == [
        ("cyc_a", "derive", ("req",)),
        ("cyc_b", "derive_by_type.req", ()),
    ]
    # without the declared types, the types no entry names are one group: the same
    assert [(p.name, p.part, p.on_types) for p in check_derive_rules(schema)] == [
        ("cyc_a", "derive", ("req",)),
        ("cyc_b", "derive_by_type.req", ()),
    ]


def test_a_cycle_through_derive_on_every_type_is_one_finding_as_before() -> None:
    """Two ``derive`` rules reading each other cycle on every type: ``derive`` cannot be
    read anywhere, reported as a project without ``derive_by_type`` reports it."""
    schema = _cycle_schema(cyc_b_derive=DeriveRule(kind="copy", field="cyc_a"))
    problems = check_derive_rules(schema, need_types=NEED_TYPES)
    assert [(p.name, p.part, p.on_types) for p in problems] == [
        ("cyc_a", "derive", ()),
        ("cyc_b", "derive", ()),
    ]
    assert problems == check_derive_rules(schema)
    # an entry on every type but one leaves the cycle on that type alone
    every_but_test = {t: DeriveRule(kind="copy", field="title") for t in NEED_TYPES}
    del every_but_test["test"]
    schema = _cycle_schema(
        cyc_b_derive=DeriveRule(kind="copy", field="cyc_a"), cyc_b=every_but_test
    )
    problems = check_derive_rules(schema, need_types=NEED_TYPES)
    assert [(p.name, p.part, p.on_types) for p in problems] == [
        ("cyc_a", "derive", ("test",)),
        ("cyc_b", "derive", ("test",)),
    ]


# -- the load checks, end to end -------------------------------------------------------

LOAD_CHECKS_TOML = """\
[needs.fields.hours]
schema = { type = "number" }

[needs.fields.unknown_type]
schema = { type = "number" }
derive_by_type.epic = { kind = "sum", field = "hours", over = "links" }
derive_by_type.req = { kind = "sum", field = "hours", over = "links" }

[needs.fields.title_key]
schema = { type = "number" }
derive_by_type.Requirement = { kind = "sum", field = "hours", over = "links" }

[needs.fields.empty_table]
schema = { type = "number" }
default = 7
derive_by_type = {}

[needs.fields.mixed_order]
schema = { type = "number" }
derive_by_type.req = { kind = "copy", field = "hours", bogus = 1 }
derive_by_type.impl = { kind = "copy", field = "nope" }

[needs.fields.not_a_table]
schema = { type = "number" }
derive_by_type = [1, 2]

[needs.fields.table_beside_derive]
schema = { type = "number" }
derive = { kind = "copy", field = "hours" }
derive_by_type = "spec"

[needs.fields.entry_not_table]
schema = { type = "number" }
derive_by_type.req = 3
derive_by_type.spec = { kind = "sum", field = "hours", over = "links" }

[needs.fields.entry_invalid]
schema = { type = "number" }
default = 9
derive_by_type.req = { kind = "sum", field = "nope", over = "links" }
derive_by_type.spec = { kind = "sum", field = "hours", over = "links" }

[needs.fields.entry_invalid_fallback]
schema = { type = "number" }
derive = { kind = "copy", field = "hours" }
derive_by_type.req = { kind = "sum", field = "nope", over = "links" }

[needs.fields.types_role]
schema = { type = "number" }
derive = { kind = "sum", field = "hours", over = "links", types = ["req"] }

[needs.fields.beside_default]
schema = { type = "number" }
default = 1
derive = { kind = "sum", field = "hours", over = "links" }
derive_by_type.spec = { kind = "copy", field = "hours" }

[needs.fields.beside_predicates]
schema = { type = "number" }
predicates = [["status == 'open'", 5]]
derive_by_type.spec = { kind = "copy", field = "hours" }

[needs.fields.dynamic_default]
schema = { type = "string" }
default = "[[copy('title')]]"
derive_by_type.spec = { kind = "copy", field = "title" }

[needs.fields.variant_default]
schema = { type = "string" }
parse_variants = true
default = "<<status == 'open': a, b>>"
derive_by_type.spec = { kind = "copy", field = "title" }

[needs.fields.wrong_default]
schema = { type = "integer" }
default = "many"
derive_by_type.spec = { kind = "count", over = "links" }

[needs.fields.ordered]
schema = { type = "number" }
derive = { kind = "copy", field = "nope" }
derive_by_type = { zzz = { kind = "copy", field = "hours" }, req = { kind = "copy" } }

[needs.fields.ordered_beside]
schema = { type = "number" }
predicates = [["status == 'open'", 5]]
derive_by_type = { zzz = { kind = "copy", field = "hours" }, req = { kind = "copy" } }

[needs.fields.status]
derive_by_type.spec = { kind = "copy", field = "title" }

[needs.fields.tags]
derive = { kind = "copy", field = "title" }
derive_by_type.spec = { kind = "copy", field = "title" }

[needs.links.parent_needs]
derive_by_type.spec = { kind = "links", where = "type == 'req'" }

[needs.links.rel]
copy = true
default = ["SPEC_1"]
derive_by_type.req = { kind = "links", where = "type == 'spec'" }

[needs.links.rel_beside]
predicates = [["status == 'open'", ["REQ_1"]]]
default = ["[[copy('id')]]"]
derive_by_type.req = { kind = "links", where = "type == 'spec'" }

[needs.links.rel_default]
default = ["REQ_1"]
derive_by_type.spec = { kind = "links", where = "type == 'req'" }

[needs.links.plain_default]
default = ["REQ_1"]
"""

LOAD_CHECKS_INDEX = """\
.. req:: A
   :id: REQ_1
   :hours: 2
   :links: SPEC_1

.. spec:: B
   :id: SPEC_1
   :hours: 4
   :links: REQ_1
"""


def _invalid(name: str, reason: str, *, entry: str = "") -> str:
    if entry:
        return (
            f"WARNING: Invalid derive of field {name!r}: derive_by_type.{entry}: "
            f"{reason}; {_CLOSED}, and on need type {entry!r} holds its empty value "
            "[needs.derive_invalid]"
        )
    return (
        f"WARNING: Invalid derive of field {name!r}: {reason}; {_CLOSED}, and holds "
        "its empty value [needs.derive_invalid]"
    )


def _by_type(name: str, reason: str) -> str:
    return (
        f"WARNING: Invalid derive_by_type of field {name!r}: {reason} "
        "[needs.derive_invalid]"
    )


def _beside(name: str, keys: str, *, default: bool = False, link: bool = False) -> str:
    verb = "are" if " and " in keys else "is"
    why = (
        "; the default of the need types without a rule must be a literal value"
        if default
        else ""
    )
    what = "link type" if link else "field"
    return (
        f"WARNING: Invalid derive of {what} {name!r}: {keys} cannot be given beside "
        f"derive_by_type, and {verb} ignored{why}; the rules apply "
        "[needs.derive_invalid]"
    )


_UNKNOWN_FIELD = (
    "the role 'field' names 'nope', which is not a field, a link type or the back "
    "links of one"
)
_NO_TABLE = "; the field cannot be set in a need or by a needextend, and no need type has a rule"
#: an unreadable derive_by_type beside a derive that stands (A-38)
_USES_DERIVE = (
    "; the field cannot be set in a need or by a needextend, and every need type uses "
    "its derive"
)


@pytest.mark.parametrize(
    "test_app", [_toml_project(LOAD_CHECKS_TOML, LOAD_CHECKS_INDEX)], indirect=True
)
def test_the_load_checks_in_their_order(test_app: Any) -> None:
    """One ``needs.derive_invalid`` per rule entry or key, in a fixed order: the core
    fields, then the fields, then the link types, each by name; within a name
    ``derive``, the ``derive_by_type`` table, its entries by need type (code point),
    then the key beside ``derive_by_type``. A core field is refused for either key; a
    default of the wrong type is the ``needs.config`` warning any default gets."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        "WARNING: needs_fields['wrong_default']['default'] value is incorrect: Cannot "
        "convert 'many' to integer [needs.config]",
        "WARNING: Invalid derive of link type 'parent_needs': a core link type cannot "
        "carry a derive rule in this release; the rule is ignored "
        "[needs.derive_invalid]",
        "WARNING: Invalid derive of field 'status': a core field cannot carry a derive "
        "rule in this release; the rule is ignored [needs.derive_invalid]",
        "WARNING: Invalid derive of field 'tags': a core field cannot carry a derive "
        "rule in this release; the rule is ignored [needs.derive_invalid]",
        "WARNING: Invalid derive of field 'beside_default': kind 'sum': 'default' "
        "cannot be given beside derive, and is ignored; the rule applies "
        "[needs.derive_invalid]",
        _beside("beside_predicates", "'predicates'"),
        _beside("dynamic_default", "'default'", default=True),
        _by_type("empty_table", "it names no need type" + _NO_TABLE),
        _invalid("entry_invalid", "kind 'sum': " + _UNKNOWN_FIELD, entry="req"),
        _invalid(
            "entry_invalid_fallback", "kind 'sum': " + _UNKNOWN_FIELD, entry="req"
        ),
        _invalid("entry_not_table", "it is not a table naming a 'kind'", entry="req"),
        # a check-time entry (impl) before a read-time one (req): by need type
        _invalid("mixed_order", "kind 'copy': " + _UNKNOWN_FIELD, entry="impl"),
        _invalid("mixed_order", "kind 'copy': 'bogus' is not a role", entry="req"),
        _by_type("not_a_table", "it is not a table of need types" + _NO_TABLE),
        _invalid("ordered", "kind 'copy': " + _UNKNOWN_FIELD),
        _invalid("ordered", "kind 'copy' requires the role 'field'", entry="req"),
        _by_type("ordered", "'zzz' is not a need type; the entry is ignored"),
        _invalid(
            "ordered_beside", "kind 'copy' requires the role 'field'", entry="req"
        ),
        _by_type("ordered_beside", "'zzz' is not a need type; the entry is ignored"),
        _beside("ordered_beside", "'predicates'"),
        _by_type(
            "table_beside_derive", "it is not a table of need types" + _USES_DERIVE
        ),
        _by_type(
            "title_key",
            "'Requirement' is not a need type (did you mean 'req'?); the entry is "
            "ignored",
        ),
        _invalid(
            "types_role",
            "kind 'sum': 'types' is not a role; a rule for some need types is "
            "declared under derive_by_type",
        ),
        _by_type("unknown_type", "'epic' is not a need type; the entry is ignored"),
        _beside("variant_default", "'default'", default=True),
        "WARNING: Invalid derive of link type 'rel': by need type: 'copy' is not "
        "available on a derived link type in this release, and is ignored; the rule "
        "applies [needs.derive_invalid]",
        _beside("rel_beside", "'default' and 'predicates'", default=True, link=True),
    ]


@pytest.mark.parametrize(
    "test_app", [_toml_project(LOAD_CHECKS_TOML, LOAD_CHECKS_INDEX)], indirect=True
)
def test_what_the_load_checks_leave(test_app: Any) -> None:
    """An ignored key, or an unreadable table, leaves the need types without a rule:
    they hold the off-type value (``empty_table``'s default on every need). An invalid
    entry leaves its type's needs the PLACEHOLDER -- not the default, not ``derive`` --
    and no other type is touched. A default beside ``derive`` is ignored (every type
    has a rule); a refused key beside ``derive_by_type`` alone is ignored. A core field
    is not derived. A literal link default is the off-type links."""
    app = test_app
    app.build()
    needs = _needs(app)
    req, spec = needs["REQ_1"], needs["SPEC_1"]
    assert (req["unknown_type"], spec["unknown_type"]) == (4.0, None)
    assert (req["title_key"], spec["title_key"]) == (None, None)
    assert (req["empty_table"], spec["empty_table"]) == (7.0, 7.0)
    # an unreadable derive_by_type adds no rule: derive stands on every type
    assert (req["table_beside_derive"], spec["table_beside_derive"]) == (2.0, 4.0)
    assert (req["entry_not_table"], spec["entry_not_table"]) == (None, 2.0)
    # the invalid req entry: its needs hold the placeholder, not the default 9
    assert (req["entry_invalid"], spec["entry_invalid"]) == (None, 2.0)
    # ... nor what derive computes on the other types
    assert (req["entry_invalid_fallback"], spec["entry_invalid_fallback"]) == (
        None,
        4.0,
    )
    assert (req["beside_default"], spec["beside_default"]) == (4.0, 4.0)
    assert (req["beside_predicates"], spec["beside_predicates"]) == (None, 4.0)
    assert (req["dynamic_default"], spec["dynamic_default"]) == (None, "B")
    assert (req["variant_default"], spec["variant_default"]) == (None, "B")
    assert (req["wrong_default"], spec["wrong_default"]) == (None, 1)
    assert (req["status"], spec["status"]) == (None, None)
    # rel's copy is not made, on any need: not even SPEC_1's off-type default
    assert (req["rel"], spec["rel"]) == (["SPEC_1"], ["SPEC_1"])
    assert (req["links"], spec["links"]) == (["SPEC_1"], ["REQ_1"])
    assert (req["rel_beside"], spec["rel_beside"]) == (["SPEC_1"], [])
    assert (req["rel_default"], spec["rel_default"]) == (["REQ_1"], ["REQ_1"])
    # the export's schema default of a link type derived by type alone is its
    # off-type links; every other link type's is unchanged
    exported = _export_schema(app)
    assert [
        exported[name]["default"]
        for name in ("rel_default", "rel", "rel_beside", "plain_default", "links")
    ] == [["REQ_1"], ["SPEC_1"], [], [], []]
    schema = SphinxNeedsData(app.env).get_schema()
    status, empty_table = (
        schema.get_core_field("status"),
        schema.get_extra_field("empty_table"),
    )
    assert status is not None and not status.derived
    assert empty_table is not None and empty_table.derive_by_type == {}


COPIED_INTO_LINKS_TOML = """\
[needs.links.links]
derive_by_type.req = { kind = "links", where = "type == 'spec'" }
derive_by_type.spec = { kind = "links", where = "" }

[needs.links.copier]
copy = true

[needs.links.copier_by_type]
copy = true
derive_by_type.req = { kind = "links", where = "type == 'spec'" }
"""

COPIED_IMPORT = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "SPEC_9": {
                    "id": "SPEC_9",
                    "type": "spec",
                    "title": "Imported",
                    "copier": ["REQ_1"],
                }
            }
        }
    },
}


@pytest.mark.parametrize(
    "test_app",
    [
        _toml_project(
            COPIED_INTO_LINKS_TOML,
            ".. req:: A\n   :id: REQ_1\n   :copier: SPEC_1\n\n"
            ".. spec:: B\n   :id: SPEC_1\n   :copier: REQ_1\n\n"
            ".. needimport:: imported.json\n",
            **{"imported.json": json.dumps(COPIED_IMPORT)},
        )
    ],
    indirect=True,
)
def test_links_derived_on_one_type_takes_no_copy(test_app: Any) -> None:
    """``links`` derived on one need type is derived: a link type copying into it is
    reported (the rule's finding, here beside ``derive_by_type``, so after its
    entries; link types by name), and nothing is copied on any need, of that type or not -- an imported
    need too, whose ``links`` no rule recomputes. A copying link type that is itself
    derived by type is reported once, for its own ``copy``, not as copying into
    ``links``."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        "WARNING: Invalid derive of link type 'copier_by_type': by need type: 'copy' "
        "is not available on a derived link type in this release, and is ignored; the "
        "rule applies [needs.derive_invalid]",
        "WARNING: Invalid derive of link type 'links': derive_by_type.spec: kind "
        "'links' has an empty 'where', which would link every need; the link type "
        "cannot be set in a need or by a needextend, and on need type 'spec' holds no "
        "links [needs.derive_invalid]",
        "WARNING: Invalid derive of link type 'links': by need type: 'links' is derived; "
        "the copy of the link type 'copier' into it is ignored; the rule applies "
        "[needs.derive_invalid]",
    ]
    needs = _needs(app)
    assert (needs["REQ_1"]["links"], needs["SPEC_1"]["links"]) == (
        ["SPEC_1", "SPEC_9"],
        [],
    )
    assert (needs["SPEC_9"]["copier"], needs["SPEC_9"]["links"]) == (["REQ_1"], [])


# -- the off-type value and the field's schema -----------------------------------------

OFF_TYPE_TOML = """\
[needs.fields.hours]
schema = { type = "number" }

[needs.fields.score]
schema = { type = "integer", minimum = 2 }
default = 1
derive_by_type.req = { kind = "count", over = "links" }

[needs.fields.zero]
schema = { type = "number", minimum = 5 }
nullable = false
default = 0
derive_by_type.req = { kind = "sum", field = "hours", over = "links" }

[needs.fields.grade]
schema = { type = "string", enum = ["open", "closed"] }
nullable = false
derive_by_type.req = { kind = "copy", field = "status" }

[needs.fields.unset]
schema = { type = "number" }
derive_by_type.req = { kind = "sum", field = "hours", over = "links" }

[needs.fields.plain]
schema = { type = "integer", minimum = 2 }
default = 1
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _toml_project(
            OFF_TYPE_TOML,
            ".. req:: A\n   :id: REQ_1\n   :status: open\n   :links: SPEC_1, SPEC_2\n\n"
            ".. spec:: B\n   :id: SPEC_1\n   :hours: 6\n\n"
            ".. spec:: C\n   :id: SPEC_2\n",
        )
    ],
    indirect=True,
)
def test_an_off_type_default_is_a_value_the_schema_checks(test_app: Any) -> None:
    """A need of a type without a rule holds the field's default as a VALUE, in the
    field's type (``0`` is ``0.0`` in a ``number`` field): the field's schema checks
    it, as it checks a plain field's default (``plain``), even where it equals the
    empty value (``zero``, not nullable: its empty value is ``0.0``). The empty value of a field without a default is the
    placeholder, which the schema does not check (``grade``'s ``""`` under an
    ``enum``); ``unset`` is nullable: ``None``. The export's schema block carries the
    default, and marks the fields ``readOnly``."""
    app = test_app
    app.build()
    violations = [w for w in build_warnings(app) if "sn_schema_violation" in w]
    assert [w for w in _warnings(app) if w not in violations] == []
    assert sorted(
        (w.split("Need path:")[1].split()[0], w.split("Field:")[1].split()[0])
        for w in violations
    ) == [
        ("REQ_1", "plain"),
        *((need, field) for need in ("SPEC_1", "SPEC_2") for field in OFF_TYPE_CHECKED),
    ]
    needs = _needs(app)
    req, spec = needs["REQ_1"], needs["SPEC_1"]
    assert (req["score"], spec["score"]) == (2, 1)
    assert (req["zero"], spec["zero"]) == (6.0, 0.0)
    assert type(spec["zero"]) is float
    assert (req["grade"], spec["grade"]) == ("open", "")
    assert (req["unset"], spec["unset"]) == (6.0, None)
    exported = _export_schema(app)
    assert {name: exported[name].get("default") for name in OFF_TYPE_FIELDS} == {
        "score": 1,
        "zero": 0,
        "grade": None,
        "unset": None,
    }
    assert "default" not in exported["grade"]
    assert all(exported[name]["readOnly"] is True for name in OFF_TYPE_FIELDS)
    assert "readOnly" not in exported["plain"]


OFF_TYPE_FIELDS = ("score", "zero", "grade", "unset")
#: the fields whose off-type value the schema refuses: the declared defaults
OFF_TYPE_CHECKED = ("plain", "score", "zero")


# -- closed on every need type ---------------------------------------------------------

CLOSED_TOML = """\
[needs.fields.hours]
schema = { type = "number" }

[needs.fields.total]
schema = { type = "number" }
default = 1
derive_by_type.req = { kind = "sum", field = "hours", over = "links" }

[needs.links.related]
derive_by_type.req = { kind = "links", where = "type == 'spec'" }
"""

CLOSED_INDEX = """\
.. req:: A
   :id: REQ_1
   :links: SPEC_1
   :total: 3

.. spec:: B
   :id: SPEC_1
   :hours: 4
   :total: 9
   :related: REQ_1

.. spec:: C
   :id: SPEC_2
   :total: [[copy("hours", "SPEC_1")]]

.. needextend:: SPEC_2
   :total: 5
   :+related: REQ_1
"""


@pytest.mark.parametrize(
    "test_app", [_toml_project(CLOSED_TOML, CLOSED_INDEX)], indirect=True
)
def test_closed_on_every_need_type(test_app: Any) -> None:
    """An authored value, an inline call and a needextend are each one
    ``needs.derive_authored`` and ignored -- on a need of a type with a rule, and on one
    without, which holds the off-type value."""
    app = test_app
    app.build()
    authored = (
        "WARNING: {} {!r} is derived ({}) and cannot be set in a need; the value {!r} "
        "is ignored [needs.derive_authored]"
    )
    extended = (
        "<srcdir>/index.rst:19: WARNING: {} {!r} is derived (by need type) and cannot "
        "be set by a needextend; the option {!r} is ignored [needs.derive_authored]"
    )
    assert _warnings(app) == [
        "<srcdir>/index.rst:4: " + authored.format("Field", "total", "kind 'sum'", "3"),
        "<srcdir>/index.rst:9: "
        + authored.format("Field", "total", "with no rule on need type 'spec'", "9"),
        "<srcdir>/index.rst:9: "
        + authored.format(
            "Link type", "related", "with no rule on need type 'spec'", "REQ_1"
        ),
        "<srcdir>/index.rst:15: "
        + authored.format(
            "Field",
            "total",
            "with no rule on need type 'spec'",
            '[[copy("hours", "SPEC_1")]]',
        ),
        extended.format("Link type", "related", "+related"),
        extended.format("Field", "total", "total"),
    ]
    needs = _needs(app)
    assert [needs[i]["total"] for i in ("REQ_1", "SPEC_1", "SPEC_2")] == [4.0, 1.0, 1.0]
    assert [needs[i]["related"] for i in ("REQ_1", "SPEC_1", "SPEC_2")] == [
        ["SPEC_1", "SPEC_2"],
        [],
        [],
    ]


# -- every spelling --------------------------------------------------------------------

SPELLINGS_CONF = """\
from sphinx_needs.api import add_field

extensions = ["sphinx_needs"]
needs_build_json = True
needs_extra_options = [
    {
        "name": "legacy",
        "schema": {"type": "string"},
        "derive_by_type": {"spec": {"kind": "copy", "field": "title"}},
    },
]
needs_extra_links = [
    {
        "option": "legacy_links",
        "derive_by_type": {"req": {"kind": "links", "where": "type == 'spec'"}},
    },
]
needs_fields = {
    "hours": {"schema": {"type": "number"}},
    "dict_form": {
        "schema": {"type": "number"},
        "default": 2,
        "derive_by_type": {"req": {"kind": "sum", "field": "hours", "over": "links"}},
    },
}
needs_links = {
    "dict_links": {"derive_by_type": {"spec": {"kind": "links", "where": "id == 'REQ_1'"}}},
}


def setup(app):
    add_field(
        "api_field",
        "per type, from an extension",
        schema={"type": "string"},
        default="none",
        derive_by_type={"req": {"kind": "copy", "field": "title"}},
    )
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            SPELLINGS_CONF,
            ".. req:: A\n   :id: REQ_1\n   :links: SPEC_1\n\n"
            ".. spec:: B\n   :id: SPEC_1\n   :hours: 4\n\n"
            ".. impl:: C\n   :id: IMPL_1\n",
        )
    ],
    indirect=True,
)
def test_every_spelling_reads_derive_by_type(test_app: Any) -> None:
    """``derive_by_type`` is read wherever ``derive`` is: a legacy
    ``needs_extra_options`` / ``needs_extra_links`` entry, the ``conf.py`` dict forms of
    ``needs_fields`` / ``needs_links``, and ``add_field`` from an extension."""
    app = test_app
    app.build()
    assert _warnings(app) == []
    needs = _needs(app)
    rows = {
        need_id: tuple(
            needs[need_id][name]
            for name in (
                "legacy",
                "legacy_links",
                "dict_form",
                "dict_links",
                "api_field",
            )
        )
        for need_id in ("REQ_1", "SPEC_1", "IMPL_1")
    }
    assert rows == {
        "REQ_1": (None, ["SPEC_1"], 4.0, [], "A"),
        "SPEC_1": ("B", [], 2.0, ["REQ_1"], "none"),
        "IMPL_1": (None, [], 2.0, [], "none"),
    }
    exported = _export_schema(app)
    assert all(
        exported[name]["readOnly"] is True
        for name in ("legacy", "legacy_links", "dict_form", "dict_links", "api_field")
    )


# -- load-time cycles per need type ----------------------------------------------------

CYCLES_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "cyc_a": {"schema": {"type": "string"}, "derive": {"kind": "copy", "field": "cyc_b"}},
    "cyc_b": {
        "schema": {"type": "string"},
        "default": "off",
        "derive_by_type": {
            "req": {"kind": "copy", "field": "cyc_a"},
            "impl": {"kind": "copy", "field": "cyc_a"},
        },
    },
    "label": {"schema": {"type": "string"}, "derive": {"kind": "copy", "field": "title"}},
    "echo": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "label"},
        "derive_by_type": {"spec": {"kind": "copy", "field": "echo"}},
    },
}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            CYCLES_CONF,
            ".. req:: A\n   :id: REQ_1\n\n.. spec:: B\n   :id: SPEC_1\n\n"
            ".. impl:: C\n   :id: IMPL_1\n\n.. test:: D\n   :id: TEST_1\n",
        )
    ],
    indirect=True,
)
def test_a_load_time_cycle_is_reported_per_need_type(test_app: Any) -> None:
    """``cyc_a``'s ``derive`` and ``cyc_b``'s ``req`` and ``impl`` entries read each
    other: each entry cannot be read, and ``derive`` cannot be read on those two types
    -- the finding names them -- while it applies on ``spec`` and ``test``, where it
    copies ``cyc_b``'s off-type default. ``echo``'s own ``spec`` entry reads itself:
    that entry alone cannot be read; its ``derive`` applies on every other type."""
    app = test_app
    app.build()
    cycle = (
        "kind 'copy': the role 'field' reads {!r}, whose rule reads this field back "
        "({}), so no need can compute it"
    )
    assert _warnings(app) == [
        "WARNING: Invalid derive of field 'cyc_a': on need types 'impl' and 'req': "
        + cycle.format("cyc_b", "cyc_a -> cyc_b -> cyc_a")
        + f"; {_CLOSED}, and on those need types holds its empty value; on every "
        "other need type the rule applies [needs.derive_invalid]",
        _invalid(
            "cyc_b", cycle.format("cyc_a", "cyc_b -> cyc_a -> cyc_b"), entry="impl"
        ),
        _invalid(
            "cyc_b", cycle.format("cyc_a", "cyc_b -> cyc_a -> cyc_b"), entry="req"
        ),
        _invalid("echo", cycle.format("echo", "echo -> echo"), entry="spec"),
    ]
    needs = _needs(app)
    order = ("REQ_1", "SPEC_1", "IMPL_1", "TEST_1")
    # on spec and test, cyc_b holds its default and cyc_a copies it
    assert [needs[i]["cyc_b"] for i in order] == [None, "off", None, "off"]
    assert [needs[i]["cyc_a"] for i in order] == [None, "off", None, "off"]
    assert [needs[i]["echo"] for i in ("REQ_1", "SPEC_1", "IMPL_1", "TEST_1")] == [
        "A",
        None,
        "C",
        "D",
    ]


# -- strata ----------------------------------------------------------------------------


def _late(what: str) -> str:
    return (
        "which is computed in the late step, after every other field (a derive rule of "
        "the kind 'hash' or 'fingerprint', or with after = \"derived\"): the "
        f"{what} is not run and the field is left empty [needs.derive_scope]"
    )


STRATA_TOML = """\
[needs.fields.num]
schema = { type = "integer" }
nullable = false
derive_by_type.req = { kind = "count", over = "links", after = "derived" }
derive_by_type.spec = { kind = "count", over = "links" }

[needs.fields.label]
schema = { type = "string" }
derive_by_type.req = { kind = "copy", field = "title", after = "derived" }
derive_by_type.spec = { kind = "copy", field = "title" }

[needs.fields.seen]
schema = { type = "string" }
derive = { kind = "copy", field = "label", over = "links" }

[needs.fields.total]
schema = { type = "number" }
"""

STRATA_INDEX = """\
.. impl:: Reader of every num
   :id: IMPL_1
   :total: [[calc_sum("num")]]

.. impl:: Reader of a late label
   :id: IMPL_2
   :links: REQ_1

.. impl:: Reader of a stratum-2 label
   :id: IMPL_3
   :links: SPEC_1

.. req:: Late
   :id: REQ_1
   :links: IMPL_1, IMPL_2

.. spec:: Not late
   :id: SPEC_1
   :links: IMPL_1
"""


@pytest.mark.parametrize(
    "test_app", [_toml_project(STRATA_TOML, STRATA_INDEX)], indirect=True
)
def test_a_read_is_decided_by_the_target_needs_rule(test_app: Any) -> None:
    """``num`` and ``label`` are late on ``req`` and not on ``spec``: a column read of
    ``num`` over every need, and a read of ``label`` over a link, are out of scope on
    the late ``REQ_1`` alone -- the finding names it, never ``SPEC_1`` -- and a read of
    ``SPEC_1``'s computes. (A field's stratum for a column read is the latest of its
    rules: the one it had last would order the column read before ``REQ_1``'s.)"""
    app = test_app
    app.build()
    assert _warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: dynamic function 'calc_sum' for option 'total' "
        f"reads 'num' on need 'REQ_1', {_late('call')}",
        "<srcdir>/index.rst:8: WARNING: derive rule 'copy' for option 'seen' reads "
        f"'label' on need 'REQ_1', {_late('rule')}",
    ]
    needs = _needs(app)
    assert (needs["REQ_1"]["num"], needs["SPEC_1"]["num"], needs["IMPL_1"]["num"]) == (
        2,
        1,
        0,
    )
    assert (needs["IMPL_1"]["total"], needs["IMPL_3"]["seen"]) == (None, "Not late")


# -- imported needs and needextend filters ---------------------------------------------

IMPORTED = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {"id": "IMP_1", "type": "spec", "title": "Off-type"},
                "IMP_2": {"id": "IMP_2", "type": "req", "title": "Rule type"},
                "IMP_3": {
                    "id": "IMP_3",
                    "type": "spec",
                    "title": "Carried",
                    "total": 42.0,
                    "grade": "high",
                },
            }
        }
    },
}

IMPORT_TOML = """\
[needs.fields.total]
schema = { type = "number" }
default = 3
derive_by_type.req = { kind = "count", over = "links" }

[needs.fields.grade]
schema = { type = "string" }
nullable = false
derive_by_type.req = { kind = "copy", field = "title" }

[needs.fields.flag]
schema = { type = "string" }
default = "off"
derive_by_type.req = { kind = "copy", field = "title" }
"""

IMPORT_INDEX = """\
.. req:: A
   :id: REQ_1

.. spec:: B
   :id: SPEC_1

.. needextend:: flag == 'off'
   :status: matched

.. needimport:: imported.json
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _toml_project(
            IMPORT_TOML, IMPORT_INDEX, **{"imported.json": json.dumps(IMPORTED)}
        )
    ],
    indirect=True,
)
def test_imported_needs_and_needextend_filters(test_app: Any) -> None:
    """No rule runs on an imported need: lacking the field, one of a type without a
    rule holds the off-type value (the default), one of a rule type its empty value
    (``None``, or ``""`` when not nullable); a carried value is kept. A needextend
    filter sees the off-type default as written -- the value is final, so the
    ``needs.derive_scope`` report names only the needs a rule computes."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        "<srcdir>/index.rst:10: WARNING: needextend filter \"flag == 'off'\" names "
        "'flag', which a dynamic function or variant computes on 1 need (REQ_1): the "
        "filter sees the value from before it is computed [needs.derive_scope]",
    ]
    needs = _needs(app)
    assert [needs[i]["total"] for i in ("IMP_1", "IMP_2", "IMP_3")] == [3.0, None, 42.0]
    assert [needs[i]["grade"] for i in ("IMP_1", "IMP_2", "IMP_3")] == ["", "", "high"]
    assert [needs[i]["flag"] for i in ("IMP_1", "IMP_2")] == ["off", None]
    assert (needs["SPEC_1"]["status"], needs["IMP_1"]["status"]) == (
        "matched",
        "matched",
    )
    assert needs["REQ_1"]["status"] is None


# -- fingerprint -----------------------------------------------------------------------

FINGERPRINT_TOML = """\
[needs.fields.hours]
schema = { type = "number" }

[needs.fields.est]
schema = { type = "number" }
default = 0
derive_by_type.req = { kind = "sum", field = "hours", over = "links" }

[needs.fields.fp]
schema = { type = "string" }
derive = { kind = "fingerprint" }

[needs.fields.fp_excluding]
schema = { type = "string" }
derive = { kind = "fingerprint", exclude = ["est"] }

[needs.links.rel]
derive_by_type.req = { kind = "links", where = "type == 'spec'" }
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _toml_project(
            FINGERPRINT_TOML,
            ".. req:: A\n   :id: REQ_1\n   :links: SPEC_1\n\n"
            ".. spec:: B\n   :id: SPEC_1\n   :hours: 4\n",
        )
    ],
    indirect=True,
)
def test_a_fingerprint_never_includes_a_field_derived_by_type(test_app: Any) -> None:
    """A field or link type with ``derive_by_type`` is derived, so no fingerprint
    includes it, on any type: the digests are those of the same project without
    ``est`` and ``rel`` (the corpus case ``by-type-fingerprint-and-hash``), and
    ``exclude`` naming one gets the text of a name a fingerprint never includes."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        _invalid(
            "fp_excluding",
            "kind 'fingerprint': the role 'exclude' names 'est', which a fingerprint "
            "never includes",
        )
    ]
    schema = SphinxNeedsData(app.env).get_schema()
    assert "est" not in fingerprint_names(schema)
    assert "rel" not in fingerprint_names(schema)
    assert "hours" in fingerprint_names(schema)
    needs = _needs(app)
    assert needs["REQ_1"]["rel"] == ["SPEC_1"]
    assert (needs["REQ_1"]["fp"], needs["SPEC_1"]["fp"]) == (
        "aff891423da89b221952ecf256e2054839ae25536b6c3cfca15806c91bf65a69",
        "bc58ea27891cd817e3a0160d1f0645eedc023dca7e52209358f376e2be541cae",
    )


GLOBAL_OPTIONS_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "label": {
        "schema": {"type": "string"},
        "derive_by_type": {"req": {"kind": "copy", "field": "title"}},
    },
}
needs_global_options = {"label": {"default": "global"}}
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(GLOBAL_OPTIONS_CONF, ".. spec:: B\n   :id: SPEC_1\n")],
    indirect=True,
)
def test_a_global_default_is_refused_as_on_any_derived_field(test_app: Any) -> None:
    """``needs_global_options`` gives a derived field no default, with
    ``derive_by_type`` as with ``derive``: the off-type value is the entry's own."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        "WARNING: needs_global_options['label']['default'] cannot be set, as field "
        "does not allow defaults [needs.config]"
    ]
    assert _needs(app)["SPEC_1"]["label"] is None


PATHS_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_types = [
    {"directive": t, "title": t, "prefix": t.upper() + "_"}
    for t in ("req", "spec", "impl", "test")
]
needs_fields = {
    "a": {"schema": {"type": "string"}, "derive": {"kind": "copy", "field": "b"}},
    "b": {
        "schema": {"type": "string"},
        "derive_by_type": {
            "impl": {"kind": "copy", "field": "a"},
            "req": {"kind": "copy", "field": "c"},
        },
    },
    "c": {
        "schema": {"type": "string"},
        "derive_by_type": {"req": {"kind": "copy", "field": "a"}},
    },
    "x": {"schema": {"type": "string"}, "derive": {"kind": "copy", "field": "y"}},
    "y": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "x"},
        "derive_by_type": {"req": {"kind": "copy", "field": "title"}},
    },
}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            PATHS_CONF,
            ".. req:: A\n   :id: REQ_1\n\n.. spec:: B\n   :id: SPEC_1\n\n"
            ".. needextend:: SPEC_1\n   :x: written\n",
        )
    ],
    indirect=True,
)
def test_a_derive_cycling_on_some_types_names_each_path(test_app: Any) -> None:
    """``a``'s ``derive`` closes a cycle on ``impl`` (``a -> b -> a``) and another on
    ``req`` (``a -> b -> c -> a``): the finding gives each type its own path. ``x``,
    declared with ``derive`` alone, cycles with ``y`` on every type but ``req`` (the github
    service's types included); it is
    still described by its own rule (``kind 'copy'``), never "by need type"."""
    app = test_app
    app.build()
    cycle = (
        "kind 'copy': the role 'field' reads {!r}, whose rule reads this field back "
        "({}), so no need can compute it"
    )
    tail = (
        f"; {_CLOSED}, and on those need types holds its empty value; on every other "
        "need type the rule applies [needs.derive_invalid]"
    )
    assert _warnings(app) == [
        "WARNING: Invalid derive of field 'a': on need type 'impl': "
        + cycle.format("b", "a -> b -> a")
        + "; on need type 'req': "
        + cycle.format("b", "a -> b -> c -> a")
        + tail,
        _invalid("b", cycle.format("a", "b -> a -> b"), entry="impl"),
        _invalid("b", cycle.format("c", "b -> c -> a -> b"), entry="req"),
        _invalid("c", cycle.format("a", "c -> a -> b -> c"), entry="req"),
        "WARNING: Invalid derive of field 'x': on need types 'commit', 'impl', "
        "'issue', 'pr', 'spec' and 'test': " + cycle.format("y", "x -> y -> x") + tail,
        "WARNING: Invalid derive of field 'y': on need types 'commit', 'impl', "
        "'issue', 'pr', 'spec' and 'test': " + cycle.format("x", "y -> x -> y") + tail,
        "<srcdir>/index.rst:10: WARNING: Field 'x' is derived (kind 'copy') and cannot "
        "be set by a needextend; the option 'x' is ignored [needs.derive_authored]",
    ]
    needs = _needs(app)
    assert (needs["REQ_1"]["x"], needs["REQ_1"]["y"]) == ("A", "A")
    assert (needs["SPEC_1"]["x"], needs["SPEC_1"]["y"]) == (None, None)
