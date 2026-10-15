"""The fields schema of one need type: ``FieldsSchema.for_type`` and its overlays.

A need type may declare a field anew (``add_type_overlay``): its needs read that
declaration in place of the one every other need type reads. A field name has one type
on every need type, so an overlay keeps the field's kind, ``type`` and ``item_type``.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from sphinx_needs.needs_schema import (
    FieldSchema,
    FieldsSchema,
    LinkDisplayConfig,
    LinkSchema,
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
    schema.add_link_field(_link("blocks"))
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
        "blocks": replace(blocks, allow_extend=True),
    }
    for field in overlays.values():
        schema.add_type_overlay("spec", field)
    return schema, overlays


def test_no_type_is_the_schema() -> None:
    schema, _ = _overlaid()
    assert schema.for_type(None) is schema


def test_a_type_without_overlays_is_the_schema() -> None:
    plain = _schema()
    assert plain.for_type("spec") is plain
    schema, _ = _overlaid()
    assert schema.for_type("req") is schema


def test_every_accessor_reads_the_overlay_else_the_field() -> None:
    """The eleven accessors of the schema of ``spec``: the overlays in place of the
    fields they replace, in the same order, every other field as it is."""
    schema, overlays = _overlaid()
    view = schema.for_type("spec")
    assert view is not schema
    assert isinstance(view, FieldsSchema)

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
    assert view.for_type(None) is schema
    assert view.for_type("req") is schema
    assert view.for_type("spec") is view


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
    assert schema.for_type("spec") is schema


def test_the_need_type_is_a_name() -> None:
    schema = _schema()
    effort = schema.get_extra_field("effort")
    assert effort is not None
    with pytest.raises(ValueError, match="need_type must be a non-empty string"):
        schema.add_type_overlay("", effort)


def test_a_change_is_seen_by_the_next_view() -> None:
    """A change to the schema after a view was resolved: the next ``for_type`` sees
    it; an overlay of the same field and need type replaces the first."""
    schema, overlays = _overlaid()
    first = schema.for_type("spec")
    effort = schema.get_extra_field("effort")
    assert effort is not None
    later = replace(effort, nullable=False)
    schema.add_type_overlay("spec", later)
    second = schema.for_type("spec")
    assert second is not first
    assert second.get_extra_field("effort") is later
    assert first.get_extra_field("effort") is effort

    again = replace(overlays["asil"], description="again")
    schema.add_type_overlay("spec", again)
    assert schema.for_type("spec").get_extra_field("asil") is again

    schema.add_extra_field(FieldSchema(name="added", schema={"type": "string"}))
    third = schema.for_type("spec")
    assert list(third.iter_extra_field_names()) == ["asil", "effort", "added"]
    assert third.get_extra_field("effort") is later


def test_an_overlay_does_not_change_the_repr() -> None:
    schema = _schema()
    before = repr(schema)
    assert before.startswith("Schema(core=[FieldSchema(name='status'")
    schema, _ = _overlaid()
    assert repr(schema) == before
