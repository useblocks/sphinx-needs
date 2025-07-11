"""Utilities for schemas in Sphinx Needs configuration (mainly validate)."""

from __future__ import annotations

from typing import Any, Literal, cast

from typeguard import TypeCheckError, check_type

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields
from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs.schema.config import (
    DISALLOWED_SCHEMA_KEYS,
    EXTRA_OPTION_BASE_TYPES_STR,
    EXTRA_OPTION_BASE_TYPES_TYPE,
    USER_CONFIG_SCHEMA_SEVERITIES,
    AllOfSchemaType,
    ExtraLinkSchemaType,
    ExtraOptionAndLinkSchemaTypes,
    ExtraOptionBooleanSchemaType,
    ExtraOptionIntegerSchemaType,
    ExtraOptionMultiValueSchemaType,
    ExtraOptionNumberSchemaType,
    ExtraOptionStringSchemaType,
    NeedFieldsSchemaType,
    SchemasRootType,
    ValidateSchemaType,
)


def validate_schemas_config(needs_config: NeedsSphinxConfig) -> None:
    """
    Validates schemas for extra_options, extra_links, and schemas in needs_config.

    Invokes the typeguard library to re-use existing type hints.
    Mostly checking for TypedDicts.
    """
    extra_option_type_map = validate_extra_option_schemas(needs_config)
    validate_extra_link_schemas(needs_config)

    if not needs_config.schemas:
        # nothing to validate
        return

    if not isinstance(needs_config.schemas, dict):
        raise NeedsConfigException("Schemas entry 'schemas' is not a dict.")

    if "schemas" not in needs_config.schemas:
        # nothing to validate
        return

    if not isinstance(needs_config.schemas["schemas"], list):
        raise NeedsConfigException("Schemas entry 'schemas' is not a list.")

    if not needs_config.schemas["schemas"]:
        # nothing to validate
        return

    # resolve $ref entries in schema
    if "$defs" in needs_config.schemas:
        defs = needs_config.schemas["$defs"]
        if "schemas" not in needs_config.schemas or not needs_config.schemas["schemas"]:
            return
        if not isinstance(needs_config.schemas["schemas"], list):
            raise NeedsConfigException("Schemas entry 'schemas' is not a list.")
        resolve_refs(defs, needs_config.schemas, set())

    # set idx for logging purposes
    for idx, schema in enumerate(needs_config.schemas["schemas"]):
        schema["idx"] = idx

    # check severity and inject default if not set
    validate_severity(needs_config.schemas["schemas"])

    # inject extra option types to schema
    extra_links = {link["option"] for link in needs_config.extra_links}
    core_field_type_map = get_core_field_type_map()
    for schema in needs_config.schemas["schemas"]:
        schema_name = get_schema_name(schema)
        populate_field_type(
            schema,
            schema_name,
            core_field_type_map,
            extra_option_type_map,
            extra_links,
        )

    # check if network links are defined as extra links
    check_network_link_types(
        needs_config.schemas["schemas"],
        extra_links,
    )

    # check schemas for disallowed keys
    for schema in needs_config.schemas["schemas"]:
        errors = check_schema_for_disallowed_keys(schema)
        if errors:
            schema_name = get_schema_name(schema)
            raise NeedsConfigException(
                f"Schema '{schema_name}' contains disallowed keys:\n"
                + "\n".join(errors)
            )

    # validate schemas against type hints at runtime
    for schema in needs_config.schemas["schemas"]:
        try:
            check_type(schema, SchemasRootType)
        except TypeCheckError as exc:
            schema_id = schema.get("id")
            idx = schema["idx"]
            schema_name = f"{schema_id}[{idx}]" if schema_id else f"[{idx}]"
            raise NeedsConfigException(
                f"Schemas entry '{schema_name}' is not valid:\n{exc}"
            ) from exc


def get_schema_name(schema: SchemasRootType) -> str:
    """Get a human-readable name for the schema considering its optional id and list index."""
    schema_id = schema.get("id")
    idx = schema["idx"]
    schema_name = f"{schema_id}[{idx}]" if schema_id else f"[{idx}]"
    return schema_name


def get_core_field_type_map() -> dict[str, EXTRA_OPTION_BASE_TYPES_TYPE]:
    core_field_type_map: dict[str, EXTRA_OPTION_BASE_TYPES_TYPE] = {}
    for core_field_name, core_field in NeedsCoreFields.items():
        if "type" in core_field["schema"]:
            core_type = core_field["schema"]["type"]
            if isinstance(core_type, str) and core_type in EXTRA_OPTION_BASE_TYPES_STR:
                core_field_type_map[core_field_name] = cast(
                    EXTRA_OPTION_BASE_TYPES_TYPE, core_type
                )
            elif (
                isinstance(core_type, list)
                and "null" in core_type
                and len(core_type) == 2
            ):
                non_null_type = next(t for t in core_type if t != "null")
                if non_null_type in EXTRA_OPTION_BASE_TYPES_STR:
                    core_field_type_map[core_field_name] = non_null_type
            else:
                # ignore the core field as the type is not supported by the schema validation
                pass
        else:
            raise NeedsConfigException(
                f"Core field '{core_field_name}' does not have a type defined in schema."
            )

    return core_field_type_map


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


def validate_extra_link_schemas(needs_config: NeedsSphinxConfig) -> None:
    """Validate types of extra links in needs_config and set default."""
    for extra_link in needs_config.extra_links:
        if "schema" not in extra_link or extra_link["schema"] is None:
            # nothing to check, leave it at None so it is explicitly unset
            continue
        if (
            "items" in extra_link["schema"]
            and "type" not in extra_link["schema"]["items"]
        ):
            # set string as default
            extra_link["schema"]["items"]["type"] = "string"
        try:
            check_type(extra_link["schema"], ExtraLinkSchemaType)
        except TypeCheckError as exc:
            raise NeedsConfigException(
                f"Schema for extra link '{extra_link['option']}' is not valid:\n{exc}"
            ) from exc


def validate_extra_option_schemas(
    needs_config: NeedsSphinxConfig,
) -> dict[str, EXTRA_OPTION_BASE_TYPES_TYPE]:
    """
    Validate types of extra options in needs_config and set default.

    :return: Map of extra option names to their types as strings.
    """
    string_type_to_typeddict_map = {
        "string": ExtraOptionStringSchemaType,
        "boolean": ExtraOptionBooleanSchemaType,
        "integer": ExtraOptionIntegerSchemaType,
        "number": ExtraOptionNumberSchemaType,
        "array": ExtraOptionMultiValueSchemaType,
    }
    option_type_map: dict[str, EXTRA_OPTION_BASE_TYPES_TYPE] = {}
    for option, value in needs_config.extra_options.items():
        if value.schema is None:
            # nothing to check, leave it at None so it is explicitly unset
            option_type_map[option] = "string"
            continue
        if "type" not in value.schema:
            # set string as default;
            # mypy is confused because it does not infer type decides about which TypedDict applies
            value.schema["type"] = "string"  # type: ignore[arg-type]
        option_type_ = value.schema["type"]
        if option_type_ not in string_type_to_typeddict_map:
            raise NeedsConfigException(
                f"Schema for extra option '{option}' has invalid type: {option_type_}. "
                f"Allowed types are: {', '.join(string_type_to_typeddict_map.keys())}"
            )
        try:
            check_type(
                value.schema,
                string_type_to_typeddict_map[option_type_],
            )
        except TypeCheckError as exc:
            raise NeedsConfigException(
                f"Schema for extra option '{option}' is not valid:\n{exc}"
            ) from exc
        option_type_map[option] = value.schema["type"]
    return option_type_map


def check_network_link_types(
    schemas: list[SchemasRootType], extra_links: set[str]
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
                    if link_type not in extra_links:
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
                    if "items" in resolved_link_schema:
                        if not isinstance(resolved_link_schema["items"], dict):
                            schema_name = get_schema_name(schema)
                            raise NeedsConfigException(
                                f"Schema '{schema_name}' defines a network link type '{link_type}' "
                                "but its 'items' value is not a dict."
                            )
                        validate_schemas.append(resolved_link_schema["items"])


def resolve_refs(
    defs: dict[
        str,
        AllOfSchemaType | NeedFieldsSchemaType | ExtraOptionAndLinkSchemaTypes,
    ],
    curr_item: Any,
    circular_refs_guard: set[str],
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
        for value in curr_item.values():
            if isinstance(value, dict):
                resolve_refs(defs, value, circular_refs_guard)
            if isinstance(value, list):
                for item in value:
                    resolve_refs(defs, item, circular_refs_guard)
    elif isinstance(curr_item, list):
        for item in curr_item:
            resolve_refs(defs, item, circular_refs_guard)


def populate_field_type(
    curr_item: Any,
    schema_name: str,
    core_field_type_map: dict[
        str, Literal["string", "integer", "number", "boolean", "array"]
    ],
    extra_option_type_map: dict[
        str, Literal["string", "integer", "number", "boolean", "array"]
    ],
    extra_links: set[str],
) -> None:
    """
    Inject field type into select / validate fields in schema.

    Users might not be aware that schema validation will not complain if e.g.
    a minimium is set for an integer, but if the type is not set, any json schema
    validator will not complain. Types are available from needs_config.extra_options.
    If the field is of type extra option but no type is defined, string is assumed.
    If the field appears as link and no type is defined, array of string is assumed.
    """
    if isinstance(curr_item, dict):
        if "properties" in curr_item:
            for key, value in curr_item["properties"].items():
                if "type" not in value:
                    if key in extra_option_type_map:
                        value["type"] = extra_option_type_map[key]
                    elif key in extra_links:
                        value["type"] = "array"
                        if "items" not in value:
                            value["items"] = {"type": "string"}
                        else:
                            if "type" not in value["items"]:
                                value["items"]["type"] = "string"
                    elif key in core_field_type_map:
                        value["type"] = core_field_type_map[key]
                    else:
                        raise NeedsConfigException(
                            f"Config error in schema '{schema_name}': Field '{key}' does not have a type defined. "
                            "Please define the type in extra_options or extra_links."
                        )
                else:
                    if (
                        key in extra_option_type_map
                        and value["type"] != extra_option_type_map[key]
                    ):
                        raise NeedsConfigException(
                            f"Config error in schema '{schema_name}': Field '{key}' has type '{value['type']}', "
                            f"but expected '{extra_option_type_map[key]}'."
                        )
        else:
            for value in curr_item.values():
                populate_field_type(
                    value,
                    schema_name,
                    core_field_type_map,
                    extra_option_type_map,
                    extra_links,
                )
    elif isinstance(curr_item, list):
        for value in curr_item:
            populate_field_type(
                value,
                schema_name,
                core_field_type_map,
                extra_option_type_map,
                extra_links,
            )


def check_schema_for_disallowed_keys(schema: Any, path: str = "") -> list[str]:
    """
    Recursively checks the provided schema for disallowed keys.

    Returns a list of error messages describing each disallowed key occurrence.
    """
    errors = []
    if isinstance(schema, dict):
        for key, value in schema.items():
            current_path = f"{path}.{key}" if path else key
            if key in DISALLOWED_SCHEMA_KEYS:
                errors.append(f"Disallowed key '{key}' found at path '{current_path}'")
            errors.extend(check_schema_for_disallowed_keys(value, current_path))
    elif isinstance(schema, list):
        for index, item in enumerate(schema):
            current_path = f"{path}[{index}]"
            errors.extend(check_schema_for_disallowed_keys(item, current_path))

    return errors


def get_default(schema: dict[str, Any], field: str | None = None) -> str | bool:
    def_value = None
    if field is None:
        if "default" in schema:
            def_value = schema["default"]
        raise KeyError("Default value not found at schema root.")
    if (
        "properties" in schema
        and field in schema["properties"]
        and "default" in schema["properties"][field]
    ):
        def_value = schema["properties"][field]["default"]
    if def_value is not None:
        if isinstance(def_value, str | bool):
            return def_value
        raise TypeError(
            f"Default value for field '{field}' is not a string or boolean."
        )
    raise KeyError(f"Default value for field '{field}' not found in schema.")
