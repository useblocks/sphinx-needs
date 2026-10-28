"""The code entity on a need created from code: the four ``code_entity*`` fields.

With ``set_code_entity`` on, every need ``src-trace`` creates from a marker (one-line
or multi-line) carries the entity its marker is attached to -- the ``scope`` of the
analysis record, projected onto need fields. A need an ``@need-ids`` reference names
gets none: it may be referenced from many places.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sphinx.config import Config as _SphinxConfig
from sphinx.util import logging

from sphinx_codelinks.analyse.entity import CodeScope
from sphinx_needs.api import add_field
from sphinx_needs.schema.config import FieldSchemaTypes

logger = logging.getLogger(__name__)

CODE_ENTITY_FIELDS: dict[str, tuple[str, FieldSchemaTypes]] = {
    "code_entity": (
        "The code entity the need is attached to: its name within its file",
        {"type": "string"},
    ),
    "code_entity_kind": (
        "What the code entity is: function, method, class, struct, namespace, ...",
        {"type": "string"},
    ),
    "code_entity_lines": (
        "The first and last line of the code entity, 1-based",
        {"type": "array", "items": {"type": "integer"}},
    ),
    "code_entity_mechanism": (
        "How the marker is attached: doc_comment, leading, trailing or enclosing",
        {"type": "string"},
    ),
}
"""The fields ``set_code_entity`` registers: name -> (description, schema)."""


def register_code_entity_fields(user_fields: set[str]) -> None:
    """Register the four fields with sphinx-needs.

    Each is ``nullable`` with no default, so a need created from a marker attached to
    no entity carries ``None``, which is stripped before schema validation.

    :param user_fields: The field names the user declares; one of the four among them
        is warned about, as codelinks registers it.
    """
    for name, (description, schema) in CODE_ENTITY_FIELDS.items():
        if name in user_fields:
            logger.warning(
                f"codelinks registers {name!r} for set_code_entity; remove the "
                "needs_fields declaration of it, or turn set_code_entity off",
                type="codelinks",
                subtype="config",
            )
        add_field(
            name,
            description,
            schema=schema,
            nullable=True,
            default=None,
        )


def _declared_schemas(config: _SphinxConfig) -> dict[str, Mapping[str, Any]]:
    """The schema of each field the user declares in ``needs_fields`` or
    ``needs_extra_options`` (empty for none: a string field)."""
    declared: dict[str, Mapping[str, Any]] = {}
    needs_fields = getattr(config, "needs_fields", None)
    if isinstance(needs_fields, dict):
        for name, params in needs_fields.items():
            schema = params.get("schema") if isinstance(params, dict) else None
            declared[str(name)] = schema if isinstance(schema, dict) else {}
    extra_options = getattr(config, "needs_extra_options", None)
    if isinstance(extra_options, list | tuple):
        for option in extra_options:
            if isinstance(option, str):
                declared.setdefault(option, {})
            elif isinstance(option, dict) and isinstance(option.get("name"), str):
                schema = option.get("schema")
                declared.setdefault(
                    option["name"], schema if isinstance(schema, dict) else {}
                )
    return declared


def _value_type(schema: Mapping[str, Any]) -> tuple[str, str | None]:
    """A field schema's value type: its ``type`` (a string by default) and, for an
    array, its items' type."""
    kind = schema.get("type", "string")
    if kind != "array":
        return str(kind), None
    items = schema.get("items")
    return "array", str(items.get("type", "string")) if isinstance(
        items, dict
    ) else "string"


def mistyped_code_entity_fields(config: _SphinxConfig) -> frozenset[str]:
    """The code entity fields the user declares with another type than codelinks
    registers them with. Their declaration stands (and is warned about), so the needs
    get no value for them rather than one the field refuses.

    :param config: The Sphinx configuration.
    :return: The names of those fields.
    """
    declared = _declared_schemas(config)
    return frozenset(
        name
        for name, (_, schema) in CODE_ENTITY_FIELDS.items()
        if name in declared and _value_type(declared[name]) != _value_type(schema)
    )


def code_entity_values(
    scope: CodeScope | None, skip: frozenset[str] = frozenset()
) -> dict[str, Any]:
    """The fields' values for a marker attached to ``scope``; none without one.

    :param scope: The ``scope`` object of the marker's analysis record.
    :param skip: Fields to leave out (:func:`mistyped_code_entity_fields`).
    :return: ``code_entity`` and ``code_entity_kind`` when the entity is named,
        ``code_entity_lines`` and ``code_entity_mechanism`` whenever it is attached.
    """
    if scope is None:
        return {}
    values: dict[str, Any] = {}
    if scope["qualified_name"] is not None:
        values["code_entity"] = scope["qualified_name"]
    if scope["entity_kind"] is not None:
        values["code_entity_kind"] = scope["entity_kind"]
    values["code_entity_lines"] = [scope["start"], scope["end"]]
    values["code_entity_mechanism"] = scope["mechanism"]
    return {name: value for name, value in values.items() if name not in skip}
