"""The fields schema of one need type: ``FieldsSchema.for_type`` and its overlays.

A need type may declare a field anew (``add_type_overlay``): its needs read that
declaration in place of the one every other need type reads. A field name has one type
on every need type, so an overlay keeps the field's kind, ``type`` and ``item_type``.
``for_type(None)`` is the global view: every field as every need type shares it. The
first ``for_type`` freezes the schema: what is read for a need type no longer changes.
"""

from __future__ import annotations

import pickle
from dataclasses import replace
from types import MappingProxyType

import pytest

from sphinx_needs.derive import DeriveRule
from sphinx_needs.needs import _report_derive_problems, _set_global_default
from sphinx_needs.needs_schema import (
    FieldLiteralValue,
    FieldSchema,
    FieldsSchema,
    LinkDisplayConfig,
    LinkSchema,
    TypeFieldsSchema,
)


def _link(name: str, **kwargs: object) -> LinkSchema:
    return LinkSchema(
        name=name,
        schema={"type": "array", "items": {"type": "string"}},
        display=LinkDisplayConfig(incoming=f"{name} in", outgoing=f"{name} out"),
        **kwargs,  # ty: ignore[invalid-argument-type]
    )


def _schema() -> FieldsSchema:
    schema = FieldsSchema()
    schema.add_core_field(
        FieldSchema(name="status", schema={"type": "string"}, nullable=True)
    )
    schema.add_core_field(
        FieldSchema(name="tags", schema={"type": "array", "items": {"type": "string"}})
    )
    schema.add_extra_field(
        FieldSchema(name="asil", schema={"type": "string"}, nullable=True),
        project=True,
    )
    schema.add_extra_field(
        FieldSchema(name="effort", schema={"type": "integer"}, nullable=True)
    )
    schema.add_link_field(_link("links"))
    schema.add_link_field(_link("blocks", allow_extend=True))
    return schema


def _overlaid() -> tuple[FieldsSchema, dict[str, FieldSchema | LinkSchema]]:
    """A schema with an overlay of a core field, an extra field and a link type on
    ``spec``."""
    schema = _schema()
    status = schema.get_core_field("status")
    asil = schema.get_extra_field("asil")
    blocks = schema.get_link_field("blocks")
    assert status is not None and asil is not None and blocks is not None
    overlays: dict[str, FieldSchema | LinkSchema] = {
        "status": replace(status, nullable=False),
        "asil": replace(asil, schema={"type": "string", "enum": ["A", "B"]}),
        "blocks": replace(blocks, allow_extend=False),
    }
    for field in overlays.values():
        schema.add_type_overlay("spec", field)
    return schema, overlays


def test_no_type_is_the_global_view() -> None:
    """``for_type(None)``: every field as every need type shares it, in full, one
    instance on every call, which is not the schema itself."""
    schema, overlays = _overlaid()
    view = schema.for_type(None)
    assert isinstance(view, TypeFieldsSchema)
    assert view is not schema
    assert schema.for_type(None) is view
    for field in schema.iter_all_fields():
        assert view.get_any_field(field.name) is field
        assert view.get_any_field(field.name) is schema.global_declaration(field.name)
    assert view.get_extra_field("asil") is not overlays["asil"]
    assert list(view.iter_all_fields()) == list(schema.iter_all_fields())


def test_a_type_without_overlays_is_the_global_view() -> None:
    plain = _schema()
    assert plain.for_type("spec") is plain.for_type(None)
    schema, _ = _overlaid()
    assert schema.for_type("req") is schema.for_type(None)
    assert schema.for_type("spec") is not schema.for_type(None)


def test_every_accessor_reads_the_overlay_else_the_field() -> None:
    """The eleven accessors of the schema of ``spec``: the overlays in place of the
    fields they replace, in the same order, every other field as it is."""
    schema, overlays = _overlaid()
    view = schema.for_type("spec")
    assert view is not schema
    assert isinstance(view, TypeFieldsSchema)

    def expected(field: FieldSchema | LinkSchema) -> FieldSchema | LinkSchema:
        return overlays.get(field.name, field)

    assert view.get_core_field("status") is overlays["status"]
    assert view.get_core_field("tags") is schema.get_core_field("tags")
    assert view.get_extra_field("asil") is overlays["asil"]
    assert view.get_extra_field("effort") is schema.get_extra_field("effort")
    assert view.get_link_field("blocks") is overlays["blocks"]
    assert view.get_link_field("links") is schema.get_link_field("links")
    for name in ("status", "tags", "asil", "effort", "links", "blocks"):
        base = schema.get_any_field(name)
        assert base is not None
        assert view.get_any_field(name) is expected(base)
    assert view.get_any_field("nope") is None
    assert view.get_extra_field("status") is None

    assert list(view.iter_all_fields()) == [
        expected(f) for f in schema.iter_all_fields()
    ]
    assert list(view.iter_core_fields()) == [
        expected(f) for f in schema.iter_core_fields()
    ]
    assert list(view.iter_extra_fields()) == [
        expected(f) for f in schema.iter_extra_fields()
    ]
    assert list(view.iter_link_fields()) == [
        expected(f) for f in schema.iter_link_fields()
    ]
    assert list(view.iter_core_field_names()) == ["status", "tags"]
    assert list(view.iter_extra_field_names()) == ["asil", "effort"]
    assert list(view.iter_link_field_names()) == ["links", "blocks"]
    assert view.is_project_field("asil")
    assert not view.is_project_field("effort")

    # the schema itself is unchanged
    assert schema.get_core_field("status") is not overlays["status"]
    assert schema.get_extra_field("asil") is not overlays["asil"]
    assert schema.get_link_field("blocks") is not overlays["blocks"]


def test_the_view_is_resolved_once() -> None:
    schema, _ = _overlaid()
    assert schema.for_type("spec") is schema.for_type("spec")


def test_the_view_of_a_view_is_the_schemas() -> None:
    schema, _ = _overlaid()
    view = schema.for_type("spec")
    assert view.for_type(None) is schema.for_type(None)
    assert view.for_type("req") is schema.for_type(None)
    assert view.for_type("spec") is view
    assert schema.for_type(None).for_type("spec") is view


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda v: v.add_core_field(
                FieldSchema(name="x", schema={"type": "string"})
            ),
            id="add_core_field",
        ),
        pytest.param(
            lambda v: v.add_extra_field(
                FieldSchema(name="x", schema={"type": "string"})
            ),
            id="add_extra_field",
        ),
        pytest.param(lambda v: v.add_link_field(_link("x")), id="add_link_field"),
        pytest.param(
            lambda v: v.replace_field(
                FieldSchema(name="effort", schema={"type": "integer"})
            ),
            id="replace_field",
        ),
        pytest.param(
            lambda v: v.add_type_overlay(
                "req", FieldSchema(name="effort", schema={"type": "integer"})
            ),
            id="add_type_overlay",
        ),
    ],
)
def test_the_view_cannot_be_changed(mutate) -> None:
    schema, _ = _overlaid()
    view = schema.for_type("spec")
    with pytest.raises(TypeError, match="need type 'spec' cannot be changed"):
        mutate(view)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda v: v.add_extra_field(
                FieldSchema(name="x", schema={"type": "string"})
            ),
            id="add_extra_field",
        ),
        pytest.param(
            lambda v: v.add_type_overlay(
                "req", FieldSchema(name="effort", schema={"type": "integer"})
            ),
            id="add_type_overlay",
        ),
        pytest.param(lambda v: v.set_need_types(["req"]), id="set_need_types"),
    ],
)
def test_the_global_view_cannot_be_changed(mutate) -> None:
    schema, _ = _overlaid()
    with pytest.raises(TypeError, match="The global view of the fields schema"):
        mutate(schema.for_type(None))


@pytest.mark.parametrize(
    "field,message",
    [
        pytest.param(
            FieldSchema(name="asil", schema={"type": "integer"}),
            "Cannot declare field 'asil' for need type 'spec' with type 'integer' "
            "(items None): its type is 'string' (items None) on every need type.",
            id="another-type",
        ),
        pytest.param(
            FieldSchema(
                name="tags", schema={"type": "array", "items": {"type": "integer"}}
            ),
            "Cannot declare field 'tags' for need type 'spec' with type 'array' "
            "(items 'integer'): its type is 'array' (items 'string') on every need "
            "type.",
            id="another-item-type",
        ),
        pytest.param(
            _link("asil"),
            "Cannot declare field 'asil' for need type 'spec': it is a field.",
            id="a-link-type-for-a-field",
        ),
        pytest.param(
            FieldSchema(
                name="links", schema={"type": "array", "items": {"type": "string"}}
            ),
            "Cannot declare field 'links' for need type 'spec': it is a link type.",
            id="a-field-for-a-link-type",
        ),
        pytest.param(
            FieldSchema(name="unknown", schema={"type": "string"}),
            "Cannot declare field 'unknown' for need type 'spec': there is no field "
            "of that name.",
            id="an-unknown-name",
        ),
    ],
)
def test_one_name_one_type(field: FieldSchema | LinkSchema, message: str) -> None:
    schema = _schema()
    with pytest.raises(ValueError) as exc_info:
        schema.add_type_overlay("spec", field)
    assert str(exc_info.value) == message
    assert schema.type_declarations(field.name) == {}


def test_the_need_type_is_a_name() -> None:
    schema = _schema()
    effort = schema.get_extra_field("effort")
    assert effort is not None
    with pytest.raises(ValueError, match="need_type must be a non-empty string"):
        schema.add_type_overlay("", effort)


def test_a_second_overlay_replaces_the_first() -> None:
    """Before the schema is read for a need type: an overlay of the same field and
    need type replaces the first, in its place; a field added later is in the view."""
    schema, overlays = _overlaid()
    effort = schema.get_extra_field("effort")
    assert effort is not None
    later = replace(effort, nullable=False)
    schema.add_type_overlay("spec", later)
    again = replace(overlays["asil"], description="again")
    schema.add_type_overlay("spec", again)
    schema.add_extra_field(FieldSchema(name="added", schema={"type": "string"}))
    assert list(schema.type_declarations("asil").values()) == [again]

    view = schema.for_type("spec")
    assert view.get_extra_field("asil") is again
    assert view.get_extra_field("effort") is later
    assert list(view.iter_extra_field_names()) == ["asil", "effort", "added"]


# -- the freeze ---------------------------------------------------------------------

FREEZE = (
    "The fields schema cannot be changed once it is complete: create_schema freezes "
    "the schema it builds, and the first read through for_type freezes one built by "
    "hand. Declare fields, link types and need types in the configuration, before "
    "the schema is built."
)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda s: s.add_core_field(
                FieldSchema(name="x", schema={"type": "string"})
            ),
            id="add_core_field",
        ),
        pytest.param(
            lambda s: s.add_extra_field(
                FieldSchema(name="x", schema={"type": "string"})
            ),
            id="add_extra_field",
        ),
        pytest.param(lambda s: s.add_link_field(_link("x")), id="add_link_field"),
        pytest.param(
            lambda s: s.replace_field(
                FieldSchema(name="effort", schema={"type": "integer"}, nullable=True)
            ),
            id="replace_field",
        ),
        pytest.param(
            lambda s: s.add_type_overlay(
                "req", FieldSchema(name="effort", schema={"type": "integer"})
            ),
            id="add_type_overlay",
        ),
        pytest.param(lambda s: s.set_need_types(["req"]), id="set_need_types"),
    ],
)
def test_the_first_read_for_a_need_type_freezes(mutate) -> None:
    """Once a need type reads the schema, no change is taken: what a need was
    created with is what every later read of its type answers."""
    schema, _ = _overlaid()
    assert not schema.frozen
    schema.for_type("req")
    assert schema.frozen
    with pytest.raises(TypeError) as exc_info:
        mutate(schema)
    assert str(exc_info.value).startswith(FREEZE)


def test_the_global_view_freezes() -> None:
    schema = _schema()
    schema.for_type(None)
    assert schema.frozen


def test_the_union_reads_do_not_freeze() -> None:
    """The shapes, the names and the declarations are read by configuration code,
    before any need: they leave the schema open."""
    schema, _ = _overlaid()
    schema.get_any_field("asil")
    list(schema.iter_all_fields())
    list(schema.iter_extra_field_names())
    schema.is_project_field("asil")
    schema.global_declaration("asil")
    schema.type_declarations("asil")
    schema.declares_default("asil")
    assert schema.need_types is None
    assert not schema.frozen


def test_freeze_is_idempotent() -> None:
    schema, overlays = _overlaid()
    schema.freeze()
    assert schema.frozen
    view = schema.for_type("spec")
    every = schema.for_type(None)
    schema.freeze()
    assert schema.for_type("spec") is view
    assert schema.for_type(None) is every
    assert view.get_extra_field("asil") is overlays["asil"]


def test_the_views_are_resolved_at_the_freeze() -> None:
    """Every need type with overlays, and the global view, are resolved when the
    schema freezes; a read after it resolves nothing."""
    schema, _ = _overlaid()
    schema.freeze()
    assert set(schema._type_views) == {"spec"}
    assert schema._global_view is not None
    view = schema._type_views["spec"]
    assert schema.for_type("spec") is view
    assert schema.for_type(None) is schema._global_view


def test_a_schema_of_one_need_type_is_frozen_from_the_start() -> None:
    """A ``TypeFieldsSchema`` is resolved, never built up: one made directly is
    frozen too."""
    view = TypeFieldsSchema()
    assert view.frozen
    with pytest.raises(TypeError) as exc_info:
        view.add_extra_field(FieldSchema(name="x", schema={"type": "string"}))
    assert str(exc_info.value) == FREEZE


def test_an_unknown_type_reads_as_the_global_view() -> None:
    """A need of a type that is not configured reads the global view: its type is
    reported where the need is created, not here."""
    schema, _ = _overlaid()
    schema.set_need_types(["req", "spec"])
    assert schema.for_type("nope") is schema.for_type(None)
    assert schema.frozen
    assert schema.for_type("nope") is schema.for_type(None)


# -- the configured need types ------------------------------------------------------


def test_an_overlay_is_of_a_configured_need_type() -> None:
    schema = _schema()
    effort = schema.get_extra_field("effort")
    assert effort is not None
    schema.set_need_types(["req", "spec"])
    assert schema.need_types == frozenset({"req", "spec"})
    with pytest.raises(ValueError) as exc_info:
        schema.add_type_overlay("nope", replace(effort, nullable=False))
    assert str(exc_info.value) == (
        "Cannot declare field 'effort' for need type 'nope': 'nope' is not a "
        "configured need type."
    )
    overlay = replace(effort, nullable=False)
    schema.add_type_overlay("spec", overlay)
    assert schema.for_type("spec").get_extra_field("effort") is overlay


def test_any_need_type_when_none_is_configured() -> None:
    schema = _schema()
    effort = schema.get_extra_field("effort")
    assert effort is not None
    assert schema.need_types is None
    overlay = replace(effort, nullable=False)
    schema.add_type_overlay("anything", overlay)
    assert schema.for_type("anything").get_extra_field("effort") is overlay


def test_the_need_types_are_set_once() -> None:
    schema = _schema()
    schema.set_need_types(["req"])
    with pytest.raises(ValueError, match="already"):
        schema.set_need_types(["req", "spec"])
    assert schema.need_types == frozenset({"req"})


def test_the_need_types_name_every_declaring_type() -> None:
    schema, _ = _overlaid()
    with pytest.raises(ValueError, match="'spec' is not a configured need type"):
        schema.set_need_types(["req"])
    assert schema.need_types is None


# -- the declarations, for configuration code ---------------------------------------


def test_the_global_declaration() -> None:
    schema, overlays = _overlaid()
    asil = schema.global_declaration("asil")
    assert isinstance(asil, FieldSchema)
    assert asil is schema.get_extra_field("asil")
    assert asil is not overlays["asil"]
    assert schema.global_declaration("blocks") is schema.get_link_field("blocks")
    assert schema.global_declaration("status") is schema.get_core_field("status")
    assert schema.global_declaration("nope") is None
    view = schema.for_type("spec")
    assert view.global_declaration("asil") is asil


def test_the_declarations_of_each_type() -> None:
    schema, overlays = _overlaid()
    declarations = schema.type_declarations("asil")
    assert isinstance(declarations, MappingProxyType)
    assert dict(declarations) == {"spec": overlays["asil"]}
    assert schema.type_declarations("effort") == {}
    assert schema.type_declarations("nope") == {}
    with pytest.raises(TypeError):
        declarations["req"] = overlays["asil"]  # ty: ignore[invalid-assignment]
    assert schema.for_type("spec").type_declarations("asil") == declarations


def test_a_default_is_declared_globally_or_by_a_type() -> None:
    """``declares_default``: the field's global declaration, or any need type's,
    carries a default or a predicate default."""
    schema = _schema()
    schema.add_extra_field(
        FieldSchema(name="plain", schema={"type": "string"}, allow_defaults=True)
    )
    schema.add_extra_field(
        FieldSchema(
            name="globally",
            schema={"type": "string"},
            allow_defaults=True,
            default=FieldLiteralValue("g"),
        )
    )
    schema.add_extra_field(
        FieldSchema(
            name="predicated",
            schema={"type": "string"},
            allow_defaults=True,
            predicate_defaults=(('status == "open"', FieldLiteralValue("p")),),
        )
    )
    by_type = FieldSchema(
        name="by_type", schema={"type": "string"}, allow_defaults=True
    )
    schema.add_extra_field(by_type)
    schema.add_type_overlay("spec", replace(by_type, default=FieldLiteralValue("t")))
    assert not schema.declares_default("plain")
    assert schema.declares_default("globally")
    assert schema.declares_default("predicated")
    assert schema.declares_default("by_type")
    assert not schema.declares_default("nope")


# -- what reads and changes the schema while it is built ----------------------------


def _with_default() -> FieldsSchema:
    schema = _schema()
    schema.add_extra_field(
        FieldSchema(name="owner", schema={"type": "string"}, allow_defaults=True)
    )
    return schema


def test_a_legacy_default_replaces_the_field() -> None:
    """``needs_global_options`` gives a default to a copy of the field, which
    replaces it, in its place: a registered field is not changed in place."""
    schema = _with_default()
    owner = schema.global_declaration("owner")
    assert owner is not None
    _set_global_default(
        schema, "needs_global_options", "owner", {"default": "me"}, allow_coercion=True
    )
    replaced = schema.global_declaration("owner")
    assert replaced is not owner
    assert owner.default is None
    assert isinstance(replaced, FieldSchema)
    assert replaced.default == FieldLiteralValue("me")
    assert list(schema.iter_extra_field_names()) == ["asil", "effort", "owner"]


def test_a_legacy_default_after_the_freeze_is_refused() -> None:
    schema = _with_default()
    schema.for_type(None)
    with pytest.raises(TypeError) as exc_info:
        _set_global_default(
            schema,
            "needs_global_options",
            "owner",
            {"default": "me"},
            allow_coercion=True,
        )
    assert str(exc_info.value).startswith(FREEZE)
    owner = schema.global_declaration("owner")
    assert owner is not None
    assert owner.default is None


def _invalid_derive() -> FieldsSchema:
    schema = _schema()
    schema.add_extra_field(
        FieldSchema(
            name="score",
            schema={"type": "string"},
            nullable=True,
            derive=DeriveRule(kind="copy", field="nope"),
        )
    )
    return schema


def test_the_schema_is_built_before_it_is_read() -> None:
    """``create_schema`` replaces a field whose rule cannot be read after every field
    is added: a read for a need type before it would refuse that replacement, so the
    schema is read for a need type only once it is built."""
    schema = _invalid_derive()
    _report_derive_problems(schema, [], {"req": "Requirement"})
    score = schema.global_declaration("score")
    assert score is not None
    assert type(score.derive).__name__ == "DeriveInvalid"

    frozen = _invalid_derive()
    frozen.for_type(None)
    with pytest.raises(TypeError) as exc_info:
        _report_derive_problems(frozen, [], {"req": "Requirement"})
    assert str(exc_info.value).startswith(FREEZE)


def test_a_frozen_schema_pickles_with_its_views() -> None:
    schema, overlays = _overlaid()
    schema.set_need_types(["req", "spec"])
    schema.freeze()
    loaded = pickle.loads(pickle.dumps(schema))
    assert loaded.frozen
    assert loaded.need_types == frozenset({"req", "spec"})
    assert repr(loaded) == repr(schema)
    view = loaded.for_type("spec")
    assert isinstance(view, TypeFieldsSchema)
    assert view.get_extra_field("asil") == overlays["asil"]
    assert view.for_type(None) is loaded.for_type(None)
    assert loaded.for_type("req") is loaded.for_type(None)
    with pytest.raises(TypeError):
        loaded.add_extra_field(FieldSchema(name="x", schema={"type": "string"}))
    with pytest.raises(TypeError, match="need type 'spec' cannot be changed"):
        view.add_extra_field(FieldSchema(name="x", schema={"type": "string"}))


def test_an_overlay_does_not_change_the_repr() -> None:
    schema = _schema()
    before = repr(schema)
    assert before.startswith("Schema(core=[FieldSchema(name='status'")
    schema, _ = _overlaid()
    assert repr(schema) == before


def test_a_type_derives_a_field_by_derive_by_type() -> None:
    """An overlay keeps the field's derivation: a field derived per need type says so
    in its ``derive_by_type``."""
    schema = _schema()
    schema.add_extra_field(
        FieldSchema(
            name="score",
            schema={"type": "number"},
            derive_by_type={"req": DeriveRule(kind="copy", field="effort")},
        )
    )
    effort = schema.get_extra_field("effort")
    score = schema.get_extra_field("score")
    assert effort is not None and score is not None
    with pytest.raises(ValueError) as exc_info:
        schema.add_type_overlay(
            "spec", replace(effort, derive=DeriveRule(kind="copy", field="status"))
        )
    assert str(exc_info.value) == (
        "Cannot declare field 'effort' for need type 'spec' with another derivation: "
        "a field is derived per need type by its derive_by_type."
    )
    with pytest.raises(ValueError) as exc_info:
        schema.add_type_overlay(
            "spec",
            replace(
                score, derive_by_type={"spec": DeriveRule(kind="copy", field="effort")}
            ),
        )
    assert str(exc_info.value) == (
        "Cannot declare field 'score' for need type 'spec' with another derivation: "
        "a field is derived per need type by its derive_by_type."
    )
    assert schema.type_declarations("effort") == {}
    assert schema.type_declarations("score") == {}


def test_a_type_without_a_rule_takes_its_own_value_of_a_derived_field() -> None:
    """An overlay may give a field derived per need type its own literal default: the
    value of that type's needs, which have no rule. The configuration refuses a default
    of a derived field; the schema itself takes it."""
    schema = _schema()
    score = FieldSchema(
        name="score",
        schema={"type": "string"},
        default=FieldLiteralValue("D"),
        derive_by_type={"req": DeriveRule(kind="copy", field="asil")},
    )
    schema.add_extra_field(score)
    schema.add_type_overlay("spec", replace(score, default=FieldLiteralValue("S")))
    spec_score = schema.for_type("spec").get_extra_field("score")
    impl_score = schema.for_type("impl").get_extra_field("score")
    assert spec_score is not None and impl_score is not None
    assert (spec_score.off_type_value(), impl_score.off_type_value()) == ("S", "D")


def test_a_replaced_field_keeps_the_type_of_its_overlays() -> None:
    """A field replaced while a need type declares it anew keeps its type and item
    type; a replacement of the same type is taken."""
    schema, _ = _overlaid()
    with pytest.raises(ValueError) as exc_info:
        schema.replace_field(FieldSchema(name="asil", schema={"type": "integer"}))
    assert str(exc_info.value) == (
        "Cannot replace field 'asil' with type 'integer' (items None): need type "
        "'spec' declares it with another type."
    )
    again = FieldSchema(
        name="asil", schema={"type": "string"}, nullable=True, description="again"
    )
    schema.replace_field(again)
    assert schema.get_extra_field("asil") is again


def test_a_replaced_field_keeps_the_item_type_of_its_overlays() -> None:
    schema = _schema()
    labels = FieldSchema(
        name="labels", schema={"type": "array", "items": {"type": "string"}}
    )
    schema.add_extra_field(labels)
    schema.add_type_overlay("spec", replace(labels, description="spec"))
    with pytest.raises(ValueError) as exc_info:
        schema.replace_field(
            FieldSchema(
                name="labels", schema={"type": "array", "items": {"type": "integer"}}
            )
        )
    assert str(exc_info.value) == (
        "Cannot replace field 'labels' with type 'array' (items 'integer'): need type "
        "'spec' declares it with another item type."
    )


def test_a_replaced_field_keeps_the_type_on_every_need_type() -> None:
    """The overlays of every need type are checked, not those of the first one."""
    schema = _schema()
    effort = schema.get_extra_field("effort")
    asil = schema.get_extra_field("asil")
    assert effort is not None and asil is not None
    schema.add_type_overlay("req", replace(effort, nullable=False))
    schema.add_type_overlay("spec", replace(asil, nullable=False))
    with pytest.raises(ValueError) as exc_info:
        schema.replace_field(FieldSchema(name="asil", schema={"type": "integer"}))
    assert str(exc_info.value) == (
        "Cannot replace field 'asil' with type 'integer' (items None): need type "
        "'spec' declares it with another type."
    )


def test_a_replaced_field_keeps_the_derivation_of_its_overlays() -> None:
    schema = _schema()
    effort = schema.get_extra_field("effort")
    assert effort is not None
    schema.add_type_overlay("spec", replace(effort, nullable=False))
    with pytest.raises(ValueError) as exc_info:
        schema.replace_field(
            replace(
                effort, derive_by_type={"req": DeriveRule(kind="copy", field="status")}
            )
        )
    assert str(exc_info.value) == (
        "Cannot replace field 'effort' with type 'integer' (items None): need type "
        "'spec' declares it with another derivation."
    )


def test_an_equal_derivation_is_the_same_derivation() -> None:
    """An overlay whose ``derive_by_type`` equals the field's, built anew, is taken."""
    schema = _schema()
    schema.add_extra_field(
        FieldSchema(
            name="score",
            schema={"type": "number"},
            nullable=True,
            derive_by_type={"req": DeriveRule(kind="copy", field="effort")},
        )
    )
    score = schema.get_extra_field("score")
    assert score is not None
    overlay = replace(
        score,
        nullable=False,
        derive_by_type={"req": DeriveRule(kind="copy", field="effort")},
    )
    schema.add_type_overlay("spec", overlay)
    assert schema.for_type("spec").get_extra_field("score") is overlay


def test_a_replaced_field_keeps_the_type_of_the_first_need_type() -> None:
    """The overlays of every need type are checked, not those of the last one."""
    schema = _schema()
    effort = schema.get_extra_field("effort")
    asil = schema.get_extra_field("asil")
    assert effort is not None and asil is not None
    schema.add_type_overlay("spec", replace(asil, nullable=False))
    schema.add_type_overlay("req", replace(effort, nullable=False))
    with pytest.raises(ValueError) as exc_info:
        schema.replace_field(FieldSchema(name="asil", schema={"type": "integer"}))
    assert str(exc_info.value) == (
        "Cannot replace field 'asil' with type 'integer' (items None): need type "
        "'spec' declares it with another type."
    )


def test_a_replaced_field_keeps_the_derive_of_its_overlays() -> None:
    schema = _schema()
    effort = schema.get_extra_field("effort")
    assert effort is not None
    schema.add_type_overlay("spec", replace(effort, nullable=False))
    with pytest.raises(ValueError) as exc_info:
        schema.replace_field(
            replace(effort, derive=DeriveRule(kind="copy", field="status"))
        )
    assert str(exc_info.value) == (
        "Cannot replace field 'effort' with type 'integer' (items None): need type "
        "'spec' declares it with another derivation."
    )


def test_an_equal_derive_is_the_same_derive() -> None:
    """An overlay whose ``derive`` equals the field's, built anew, is taken."""
    schema = _schema()
    schema.add_extra_field(
        FieldSchema(
            name="score",
            schema={"type": "number"},
            nullable=True,
            derive=DeriveRule(kind="copy", field="effort"),
        )
    )
    score = schema.get_extra_field("score")
    assert score is not None
    overlay = replace(
        score, nullable=False, derive=DeriveRule(kind="copy", field="effort")
    )
    schema.add_type_overlay("spec", overlay)
    assert schema.for_type("spec").get_extra_field("score") is overlay


def test_a_replacement_names_everything_it_changes() -> None:
    schema = _schema()
    effort = schema.get_extra_field("effort")
    assert effort is not None
    schema.add_type_overlay("spec", replace(effort, nullable=False))
    with pytest.raises(ValueError) as exc_info:
        schema.replace_field(
            FieldSchema(
                name="effort",
                schema={"type": "array", "items": {"type": "integer"}},
                derive=DeriveRule(kind="copy", field="status"),
            )
        )
    assert str(exc_info.value) == (
        "Cannot replace field 'effort' with type 'array' (items 'integer'): need type "
        "'spec' declares it with another type, item type and derivation."
    )
