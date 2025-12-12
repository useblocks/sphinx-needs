"""Generate JSON schema from TypedDict definitions.

Used to generate the JSON schema for sphinx-needs configuration validation,
without needing to manually write the schema or have pydantic as a runtime dependency.
"""

from pathlib import Path
from sys import version_info
from types import UnionType
from typing import (
    Annotated,
    Any,
    TypedDict,
    Union,
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


def _resolve_typeddict_types(tp, cache):
    """Recursively map type hints so that nested TypedDicts become Pydantic models."""
    origin = get_origin(tp)
    args = get_args(tp)

    # case: Annotated[T, ...]
    if origin is Annotated:
        # inner = args[0]
        # TODO the * syntax is not supported in python 3.10
        raise NotImplementedError("Annotated types are not yet supported")
        # return Annotated[resolve_typeddict_types(inner, cache), *args[1:]]

    # case: nested TypedDict
    if (
        isinstance(tp, type)
        and issubclass(tp, dict)
        and hasattr(tp, "__required_keys__")
    ):
        return _typed_dict_to_model(tp.__name__ + "Model", tp, cache)

    # case: list[T]
    if origin is list:
        return list[_resolve_typeddict_types(args[0], cache)]

    # case: dict[K, V]
    if origin is dict:
        return dict[
            _resolve_typeddict_types(args[0], cache),
            _resolve_typeddict_types(args[1], cache),
        ]

    # case: Union, Optional, etc.
    if (
        origin is UnionType or origin is None
    ):  # Python 3.10-3.11 feature; ensure correct import
        origin = get_origin(tp)

    if origin is None:
        # simple type
        return tp

    if origin is Union:
        return Union[tuple(_resolve_typeddict_types(a, cache) for a in args)]  # noqa: UP007

    return tp


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
