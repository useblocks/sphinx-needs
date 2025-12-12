"""Generate JSON schema from TypedDict definitions.

Used to generate the JSON schema for sphinx-needs configuration validation,
without needing to manually write the schema or have pydantic as a runtime dependency.
"""

from pathlib import Path
from sys import version_info
from typing import (
    Any,
    TypedDict,
    get_args,
    get_origin,
    get_type_hints,
)

import pytest
from syrupy.extensions.json import JSONSnapshotExtension

from sphinx_needs.schema.config import (
    ExtraLinkItemSchemaType,
    ExtraLinkSchemaType,
    ExtraOptionBooleanSchemaType,
    ExtraOptionIntegerSchemaType,
    ExtraOptionMultiValueSchemaType,
    ExtraOptionNumberSchemaType,
    ExtraOptionStringSchemaType,
    SchemasRootType,
)


def _unwrap_pep655(annotation):
    """Unwrap NotRequired[T] and Required[T] annotations."""
    from typing_extensions import NotRequired, Required

    origin = get_origin(annotation)
    if origin is NotRequired:
        inner = get_args(annotation)[0]
        return inner, False  # optional
    if origin is Required:
        inner = get_args(annotation)[0]
        return inner, True  # required
    return annotation, None  # None = infer from TypedDict.__required_keys__


def _typed_dict_to_model(name: str, td: type):
    """Convert a TypedDict to a Pydantic model."""
    from pydantic import BaseModel, ConfigDict, create_model

    hints = get_type_hints(td, include_extras=True)

    total = getattr(td, "__total__", True)
    required_keys = getattr(td, "__required_keys__", set())
    required = []
    fields = {}

    for key, ann in hints.items():
        unwrapped_type, explicit_required = _unwrap_pep655(ann)

        # Decide if field is required
        if explicit_required is True or (
            explicit_required is None and key in required_keys
        ):
            required.append(key)

        fields[key] = (unwrapped_type, ...)

    class BaseClass(BaseModel):
        model_config = ConfigDict(extra="forbid" if total else "allow")

        @classmethod
        def model_json_schema(cls):
            schema = super().model_json_schema()
            schema["required"] = required
            return schema

    return create_model(name, **fields, __base__=BaseClass)


def typed_dict_to_json_schema(td: type[TypedDict]) -> dict[str, Any]:
    """Convert a TypedDict to a JSON schema."""
    from pydantic.json_schema import GenerateJsonSchema

    model = _typed_dict_to_model(td.__name__ + "Model", td)
    data = model.model_json_schema()
    data["$schema"] = GenerateJsonSchema.schema_dialect
    return data


class SchemaJSONExtension(JSONSnapshotExtension):
    @classmethod
    def dirname(cls, *, test_location) -> str:
        return str(
            Path(__file__).parent.parent.parent.joinpath(
                "sphinx_needs", "schema", "jsons"
            )
        )

    @classmethod
    def get_snapshot_name(cls, *, test_location, index: str) -> str:
        return f"{index}.schema"


@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(SchemaJSONExtension)


@pytest.mark.skipif(version_info[:2] != (3, 12), reason="Only run on Python 3.12")
@pytest.mark.parametrize(
    "klass",
    [
        ExtraLinkItemSchemaType,
        ExtraLinkSchemaType,
        ExtraOptionBooleanSchemaType,
        ExtraOptionIntegerSchemaType,
        ExtraOptionMultiValueSchemaType,
        ExtraOptionNumberSchemaType,
        ExtraOptionStringSchemaType,
        SchemasRootType,
    ],
)
def test_generate_schema(klass, snapshot_json):
    schema = typed_dict_to_json_schema(klass)
    assert schema == snapshot_json(name=klass.__name__)
