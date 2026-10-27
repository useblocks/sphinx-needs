"""A need type's declaration of a link type's back links: ``BackLinksSchema``.

A ``[needs.types.<t>.links.<l>_back]`` entry declares how many links of ``l`` point to
a need of the type (``minItems``, ``maxItems``) and the severity of a need failing the
count. The configuration's behaviour is pinned by the fields-per-type conformance
corpus (section "the count of a link type's back links"); these tests pin the schema
object itself: what a declaration may hold, where it is registered, and which schema
of one need type reads it.
"""

from __future__ import annotations

from typing import Any

import pytest

from sphinx_needs.needs_schema import (
    BackLinksSchema,
    FieldsSchema,
    LinkDisplayConfig,
    LinkSchema,
)


def _schema(*need_types: str) -> FieldsSchema:
    schema = FieldsSchema()
    schema.add_link_field(
        LinkSchema(
            name="satisfies",
            schema={"type": "array", "items": {"type": "string"}},
            display=LinkDisplayConfig(incoming="satisfied by", outgoing="satisfies"),
        )
    )
    if need_types:
        schema.set_need_types(need_types)
    return schema


def _back(**kwargs: Any) -> BackLinksSchema:
    return BackLinksSchema(
        name="satisfies_back", link_type="satisfies", **{"schema": {}, **kwargs}
    )


@pytest.mark.parametrize(
    "schema",
    [
        pytest.param({"uniqueItems": True}, id="another-keyword"),
        pytest.param({"minItems": -1}, id="negative"),
        pytest.param({"minItems": True}, id="a-boolean"),
        pytest.param({"maxItems": 1.0}, id="a-float"),
    ],
)
def test_a_count_is_min_items_and_max_items(schema: dict[str, Any]) -> None:
    """Only ``minItems`` and ``maxItems``, each a non-negative integer."""
    with pytest.raises(ValueError, match="schema must give only 'minItems'"):
        _back(schema=schema)


def test_a_declaration_names_its_link_types_back_links() -> None:
    with pytest.raises(ValueError, match="name must be the link type's name"):
        BackLinksSchema(name="satisfies", link_type="satisfies", schema={})


def test_a_declaration_takes_a_severity_of_three() -> None:
    with pytest.raises(ValueError, match="severity must be one of"):
        _back(severity="error")
    assert _back().failure_severity == "violation"
    assert _back(severity="info").failure_severity == "info"


def test_its_json_schema_is_a_list_of_ids_counted() -> None:
    assert _back(schema={"minItems": 1, "maxItems": 2}).json_schema() == {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
        "maxItems": 2,
    }


def test_the_schema_of_its_need_type_reads_it() -> None:
    """A need type that declares only a count of back links (no overlay) has a schema
    of its own, which reads the count; the global view and every other type read none."""
    schema = _schema("req", "spec")
    back = _back(schema={"minItems": 1})
    schema.add_back_links("req", back)
    schema.freeze()
    assert dict(schema.for_type("req").back_links()) == {"satisfies_back": back}
    assert schema.for_type("req") is not schema.for_type(None)
    assert dict(schema.for_type("spec").back_links()) == {}
    assert dict(schema.for_type(None).back_links()) == {}
    assert dict(schema.back_links()) == {}


@pytest.mark.parametrize(
    ("need_type", "back", "message"),
    [
        pytest.param(
            "test",
            _back(),
            "'test' is not a configured need type",
            id="an-unknown-need-type",
        ),
        pytest.param(
            "req",
            BackLinksSchema(name="verifies_back", link_type="verifies", schema={}),
            "there is no link type 'verifies'",
            id="an-unknown-link-type",
        ),
    ],
)
def test_a_declaration_is_refused(
    need_type: str, back: BackLinksSchema, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _schema("req").add_back_links(need_type, back)


def test_a_frozen_schema_takes_no_declaration() -> None:
    schema = _schema("req")
    schema.freeze()
    with pytest.raises(TypeError, match="cannot be changed once it is complete"):
        schema.add_back_links("req", _back())


def test_a_schema_told_its_types_after_a_declaration_checks_it() -> None:
    schema = _schema()
    schema.add_back_links("req", _back())
    with pytest.raises(ValueError, match="'req' is not a configured need type"):
        schema.set_need_types(["spec"])
