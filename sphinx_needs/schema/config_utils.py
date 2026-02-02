"""Utilities for schemas in Sphinx Needs configuration (mainly validate)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

import jsonschema_rs
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs.logging import get_logger
from sphinx_needs.needs_schema import FieldsSchema
from sphinx_needs.schema.config import (
    FIELD_BASE_TYPES_STR,
    USER_CONFIG_SCHEMA_SEVERITIES,
    AllOfSchemaType,
    ExtraOptionAndLinkSchemaTypes,
    NeedFieldsSchemaType,
    RefItemType,
    ResolvedLinkSchemaType,
    SchemasRootType,
    ValidateSchemaType,
    get_schema_name,
    validate_schemas_root_type,
)
from sphinx_needs.schema.core import validate_object_schema_compiles

log = get_logger(__name__)


def validate_schemas_config(app: Sphinx, needs_config: NeedsSphinxConfig) -> None:
    """Check the schema definitions in the config for basic issues."""

    orig_debug_path = Path(needs_config.schema_debug_path)
    if not orig_debug_path.is_absolute():
        # make it relative to confdir
        needs_config.schema_debug_path = str(
            (Path(app.confdir) / orig_debug_path).resolve()
        )

    if not needs_config.schema_definitions:
        # nothing to validate, resolve or inject
        return

    if not isinstance(needs_config.schema_definitions, dict):
        raise NeedsConfigException("needs_schema_definitions is not a dict.")

    if "schemas" not in needs_config.schema_definitions:
        # nothing to validate (also no need to check for $defs)
        return

    if not isinstance(needs_config.schema_definitions["schemas"], list):
        raise NeedsConfigException(
            "The 'schemas' key in needs_schema_definitions is not a list."
        )

    if not needs_config.schema_definitions["schemas"]:
        # nothing to validate
        return

    # resolve $ref entries in schema; this is done before the type check
    # to check the final schema structure and give feedback based on it
    if "$defs" in needs_config.schema_definitions:
        defs = needs_config.schema_definitions["$defs"]
        resolve_refs(defs, needs_config.schema_definitions, set())

    # set idx for logging purposes, it's part of the schema name
    for idx, schema in enumerate(needs_config.schema_definitions["schemas"]):
        if not isinstance(schema, dict):
            raise NeedsConfigException(
                f"Schema entry at index {idx} in needs_schema_definitions.schemas is not a dict."
            )
        schema["idx"] = idx

    # check severity and inject default if not set
    validate_severity(needs_config.schema_definitions["schemas"])


def resolve_schemas_config(
    app: Sphinx, env: BuildEnvironment, _docnames: list[str]
) -> None:
    """Validates schema definitions and inject type information."""
    needs_config = NeedsSphinxConfig(app.config)

    if not (
        needs_config.schema_definitions
        and "schemas" in needs_config.schema_definitions
        and needs_config.schema_definitions["schemas"]
    ):
        return

    fields_schema = SphinxNeedsData(env).get_schema()

    # inject extra/link/core option types to each nested schema, to avoid silent json schema
    # failures; this must happens before the type check, because it requires type fields
    for schema in needs_config.schema_definitions["schemas"]:
        schema_name = get_schema_name(schema)
        populate_field_type(
            schema,
            schema_name,
            fields_schema,
        )

    # validate schemas against type hints at runtime
    for schema in needs_config.schema_definitions["schemas"]:
        try:
            validate_schemas_root_type(schema)
        except TypeError as exc:
            schema_name = get_schema_name(schema)
            raise NeedsConfigException(
                f"Schemas entry '{schema_name}' is not valid:\n{exc}"
            ) from exc

    # after type check, we can safely walk the schema for nested checks;
    # check if network links are defined as extra links
    check_network_links_against_extra_links(
        needs_config.schema_definitions["schemas"],
        fields_schema,
    )

    # check recursively all internal schemas compile
    for idx, schema in enumerate(needs_config.schema_definitions["schemas"]):
        if "select" in schema:
            try:
                validate_object_schema_compiles(schema["select"])
            except jsonschema_rs.ValidationError as exc:
                raise NeedsConfigException(
                    f"schema for 'needs_schema_definitions.{idx}.select' is not valid:\n{exc}"
                ) from exc
        _recursive_validate(
            schema["validate"], ("needs_schema_definitions", str(idx), "validate")
        )


def _recursive_validate(validate: ValidateSchemaType, path: tuple[str, ...]) -> None:
    """Recursively validate nested schemas in validate."""
    if "local" in validate:
        try:
            validate_object_schema_compiles(validate["local"])
        except jsonschema_rs.ValidationError as exc:
            path_str = ".".join((*path, "local"))
            raise NeedsConfigException(
                f"schema for '{path_str}' is not valid:\n{exc}"
            ) from exc
    for key, value in validate.get("network", {}).items():
        if "items" in value:
            _recursive_validate(value["items"], (*path, "network", key, "items"))
        if "contains" in value:
            _recursive_validate(value["contains"], (*path, "network", key, "contains"))


def validate_severity(schemas: list[SchemasRootType]) -> None:
    severity_values = {item.name for item in USER_CONFIG_SCHEMA_SEVERITIES}
    for schema in schemas:
        schema_id = schema.get("id")
        idx = schema["idx"]
        schema_name = f"{schema_id}[{idx}]" if schema_id else f"[{idx}]"

        # check severity and
        if "severity" not in schema:
            # set default severity
            schema["severity"] = "violation"
        else:
            if schema["severity"] not in severity_values:
                raise NeedsConfigException(
                    f"Schemas entry '{schema_name}' has unknown severity: {schema['severity']}"
                )


def check_network_links_against_extra_links(
    schemas: list[SchemasRootType], fields_schema: FieldsSchema
) -> None:
    """Check if network links are defined as extra links."""
    for schema in schemas:
        validate_schemas: list[ValidateSchemaType] = [schema["validate"]]
        while validate_schemas:
            validate_schema = validate_schemas.pop()
            if "network" in validate_schema:
                for link_type, resolved_link_schema in validate_schema[
                    "network"
                ].items():
                    if fields_schema.get_link_field(link_type) is None:
                        schema_name = get_schema_name(schema)
                        raise NeedsConfigException(
                            f"Schema '{schema_name}' defines an unknown network link type"
                            f" '{link_type}'."
                        )
                    if not isinstance(resolved_link_schema, dict):
                        schema_name = get_schema_name(schema)
                        raise NeedsConfigException(
                            f"Schema '{schema_name}' defines a network link type '{link_type}' "
                            "but its value a not dict."
                        )
                    nested_fields = ["contains", "items"]
                    for field in nested_fields:
                        if field in resolved_link_schema:
                            if not isinstance(resolved_link_schema[field], dict):  # type: ignore[literal-required]
                                schema_name = get_schema_name(schema)
                                raise NeedsConfigException(
                                    f"Schema '{schema_name}' defines a network link type '{link_type}' "
                                    f"but its '{field}' value is not a dict."
                                )
                            validate_schemas.append(resolved_link_schema[field])  # type: ignore[literal-required]


def resolve_refs(
    defs: dict[
        str,
        AllOfSchemaType | NeedFieldsSchemaType | ExtraOptionAndLinkSchemaTypes,
    ],
    curr_item: Any,
    circular_refs_guard: set[str],
    is_defs: bool = False,
) -> None:
    """Recursively resolve and replace $ref entries in schemas."""
    if isinstance(curr_item, dict):
        if "$ref" in curr_item:
            if len(curr_item) == 1:
                ref_raw = curr_item["$ref"]
                if not isinstance(ref_raw, str):
                    raise NeedsConfigException(
                        f"Invalid $ref value: {ref_raw}, expected a string."
                    )
                if not ref_raw.startswith("#/$defs/"):
                    raise NeedsConfigException(
                        f"Invalid $ref value: {ref_raw}, expected to start with '#/$defs/'."
                    )
                ref = ref_raw[8:]  # Remove '#/$defs/' prefix
                if ref not in defs:
                    raise NeedsConfigException(
                        f"Reference '{ref}' not found in definitions."
                    )
                if ref in circular_refs_guard:
                    raise NeedsConfigException(
                        f"Circular reference detected for '{ref}'."
                    )
                circular_refs_guard.add(ref)
                curr_item.clear()
                curr_item.update(defs[ref])
                resolve_refs(defs, curr_item, circular_refs_guard)
                circular_refs_guard.remove(ref)
            else:
                raise NeedsConfigException(
                    f"Invalid $ref entry, expected a single $ref key: {curr_item}"
                )
        for key, value in curr_item.items():
            if isinstance(value, dict):
                if is_defs:
                    circular_refs_guard.add(key)
                resolve_refs(defs, value, circular_refs_guard, is_defs=(key == "$defs"))
                if is_defs:
                    circular_refs_guard.remove(key)
            if isinstance(value, list):
                for item in value:
                    resolve_refs(defs, item, circular_refs_guard)
    elif isinstance(curr_item, list):
        for item in curr_item:
            resolve_refs(defs, item, circular_refs_guard)


def populate_field_type(
    schema: SchemasRootType,
    schema_name: str,
    fields_schema: FieldsSchema,
) -> None:
    """
    Inject field type into select / validate fields in schema.

    This is a type-directed implementation that surgically walks through the
    typed structure of SchemasRootType, rather than using runtime keyword detection.

    :param schema: The root schema being processed.
        This is not yet validated, but is expected to be dereferenced already.
    :param schema_name: The name/identifier of the schema for error reporting
    :param fields_schema: The fields schema containing field definitions
    """
    try:
        # Handle 'select' (optional)
        if "select" in schema:
            select = schema["select"]
            if isinstance(select, dict):
                _process_need_fields_schema(
                    select, schema_name, fields_schema, "select"
                )

        # Handle 'validate' (may not be present if schema is malformed)
        if "validate" in schema:
            validate = schema["validate"]
            if isinstance(validate, dict):
                _process_validate_schema(
                    validate, schema_name, fields_schema, "validate"
                )
    except NeedsConfigException:
        # Re-raise our own exceptions
        raise
    except Exception as exc:
        # Catch unexpected errors due to malformed schema structure
        raise NeedsConfigException(
            f"Unexpected error while processing schema '{schema_name}': {exc}"
        ) from exc


def _process_validate_schema(
    validate: ValidateSchemaType,
    schema_name: str,
    fields_schema: FieldsSchema,
    path: str,
) -> None:
    """Process ValidateSchemaType - has local and network fields."""
    # Handle 'local' (optional)
    if "local" in validate:
        local = validate["local"]
        if isinstance(local, dict):
            _process_need_fields_schema(
                local, schema_name, fields_schema, f"{path}.local"
            )

    # Handle 'network' (optional) - dict of link_name -> ResolvedLinkSchemaType
    if "network" in validate:
        network = validate["network"]
        if isinstance(network, dict):
            for link_name, resolved_link in network.items():
                if isinstance(resolved_link, dict):
                    _process_resolved_link(
                        resolved_link,
                        schema_name,
                        fields_schema,
                        f"{path}.network.{link_name}",
                    )


def _process_resolved_link(
    resolved: ResolvedLinkSchemaType,
    schema_name: str,
    fields_schema: FieldsSchema,
    path: str,
) -> None:
    """Process ResolvedLinkSchemaType - inject 'array' type, recurse into items/contains."""
    # Inject type="array" for the resolved link array (always an array of needs)
    if "type" not in resolved:
        resolved["type"] = "array"

    # 'items' contains ValidateSchemaType (recursive)
    if "items" in resolved:
        items = resolved["items"]
        if isinstance(items, dict):
            _process_validate_schema(items, schema_name, fields_schema, f"{path}.items")

    # 'contains' contains ValidateSchemaType (recursive)
    if "contains" in resolved:
        contains = resolved["contains"]
        if isinstance(contains, dict):
            _process_validate_schema(
                contains, schema_name, fields_schema, f"{path}.contains"
            )


def _process_need_fields_schema(
    schema: RefItemType | AllOfSchemaType | NeedFieldsSchemaType,
    schema_name: str,
    fields_schema: FieldsSchema,
    path: str,
) -> None:
    """Process a schema that could be RefItemType, AllOfSchemaType, or NeedFieldsSchemaType."""
    # Skip if it's a $ref (should be resolved by this point, but guard for type safety)
    if "$ref" in schema:
        return

    # Cast to NeedFieldsSchemaType for property access (safe after $ref check)
    need_schema = cast(NeedFieldsSchemaType, schema)

    # Inject 'object' type if properties/required/unevaluatedProperties exist
    if (
        "properties" in need_schema
        or "required" in need_schema
        or "unevaluatedProperties" in need_schema
    ):
        if "type" not in need_schema:
            need_schema["type"] = "object"
        elif need_schema["type"] != "object":
            raise NeedsConfigException(
                f"Config error in schema '{schema_name}' at path '{path}': "
                f"Schema has object keywords but type is '{need_schema['type']}', expected 'object'."
            )

    # Process properties - THE KEY INJECTION POINT
    if "properties" in need_schema:
        properties = need_schema["properties"]
        if isinstance(properties, dict):
            properties_path = f"{path}.properties"
            for field_name, field_schema in properties.items():
                if isinstance(field_name, str) and isinstance(field_schema, dict):
                    _inject_field_type(
                        field_name,
                        field_schema,
                        schema_name,
                        fields_schema,
                        f"{properties_path}.{field_name}",
                    )

    # Handle allOf (recurse into each element)
    if "allOf" in need_schema:
        all_of = need_schema["allOf"]
        if isinstance(all_of, list):
            for idx, item in enumerate(all_of):
                if isinstance(item, dict):
                    _process_need_fields_schema(
                        item, schema_name, fields_schema, f"{path}.allOf[{idx}]"
                    )


def _inject_field_type(
    field_name: str,
    field_schema: ExtraOptionAndLinkSchemaTypes,
    schema_name: str,
    fields_schema: FieldsSchema,
    path: str,
) -> None:
    """Inject type into a single field schema based on FieldsSchema lookup."""
    if (extra_field := fields_schema.get_extra_field(field_name)) is not None:
        _inject_type_and_item_type(
            field_schema,
            extra_field.type,
            extra_field.item_type,
            field_name,
            schema_name,
            path,
        )
    elif (link_field := fields_schema.get_link_field(field_name)) is not None:
        # Link fields are always array of strings
        _inject_type_and_item_type(
            field_schema,
            link_field.type,
            link_field.item_type,
            field_name,
            schema_name,
            path,
        )
    elif (core_field := fields_schema.get_core_field(field_name)) is not None:
        _inject_type_and_item_type(
            field_schema,
            core_field.type,
            core_field.item_type,
            field_name,
            schema_name,
            path,
        )
    else:
        # Fallback to NeedsCoreFields lookup (for core fields not yet in FieldsSchema)
        core_field_result = _get_core_field_type(field_name)
        if core_field_result is None:
            raise NeedsConfigException(
                f"Config error in schema '{schema_name}' at path '{path}': "
                f"Field '{field_name}' is not a known extra option, extra link, or core field."
            )
        field_type, item_type = core_field_result
        _inject_type_and_item_type(
            field_schema,
            field_type,
            item_type,
            field_name,
            schema_name,
            path,
        )


def _get_core_field_type(
    field_name: str,
) -> (
    tuple[
        Literal["string", "boolean", "integer", "number", "array"],
        None | Literal["string", "boolean", "integer", "number"],
    ]
    | None
):
    """
    Get the core field type and item type (if array) for a given core field name.

    This should eventually come from FieldsSchema, but it does not feature all
    core fields (yet).
    """
    if field_name not in NeedsCoreFields:
        return None
    field = NeedsCoreFields[field_name]
    assert "schema" in field
    assert isinstance(field["schema"], dict)
    assert "type" in field["schema"]
    schema_type = field["schema"]["type"]
    core_type: Literal["string", "boolean", "integer", "number", "array"] | None = None
    if isinstance(schema_type, str):
        core_type = cast(
            Literal["string", "boolean", "integer", "number", "array"], schema_type
        )
    elif (
        isinstance(schema_type, list)
        and "null" in schema_type
        and len(schema_type) == 2
    ):
        non_null_type = next(t for t in schema_type if t != "null")
        if non_null_type in FIELD_BASE_TYPES_STR:
            core_type = non_null_type
    if core_type is None:
        return None
    if core_type == "array":
        item_type = field["schema"].get("items", {}).get("type")
        if isinstance(item_type, str):
            return core_type, cast(
                Literal["string", "boolean", "integer", "number"], item_type
            )
        else:
            # array without items type is unexpected
            return None
    return core_type, None


def _inject_type_and_item_type(
    field_schema: ExtraOptionAndLinkSchemaTypes,
    expected_type: Literal["string", "boolean", "integer", "number", "array"],
    expected_item_type: Literal["string", "boolean", "integer", "number"] | None,
    field_name: str,
    schema_name: str,
    path: str,
) -> None:
    """Inject type and item type (for arrays) into a field schema, validating any existing values."""
    # Cast to dict for mutation (TypedDict union makes direct assignment complex)
    schema_dict = cast(dict[str, Any], field_schema)

    # Inject or validate the main type
    if "type" not in schema_dict:
        schema_dict["type"] = expected_type
    elif schema_dict["type"] != expected_type:
        raise NeedsConfigException(
            f"Config error in schema '{schema_name}' at path '{path}': "
            f"Field '{field_name}' has type '{schema_dict['type']}', but expected '{expected_type}'."
        )

    # For array types, also inject/validate item types in 'items' and 'contains'
    if expected_type == "array" and expected_item_type is not None:
        for container_key in ("items", "contains"):
            if container_key in schema_dict:
                container = schema_dict[container_key]
                container_path = f"{path}.{container_key}"
                if "type" not in container:
                    container["type"] = expected_item_type
                elif container["type"] != expected_item_type:
                    raise NeedsConfigException(
                        f"Config error in schema '{schema_name}' at path '{container_path}': "
                        f"Field '{field_name}' has {container_key}.type '{container['type']}', "
                        f"but expected '{expected_item_type}'."
                    )
