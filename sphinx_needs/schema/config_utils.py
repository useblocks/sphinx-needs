"""Utilities for schemas in Sphinx Needs configuration (mainly validate)."""

from __future__ import annotations

import re
from typing import Any, Literal, cast

from typeguard import TypeCheckError, check_type

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields
from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs.schema.config import (
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
    extra_option_type_map = inject_type_and_validate_extra_option_schemas(needs_config)
    validate_extra_link_schemas(needs_config)
    inject_type_extra_link_schemas(needs_config)

    # check for disallowed regex patterns
    validate_regex_patterns_extra_options(needs_config)
    validate_regex_patterns_extra_links(needs_config)

    if not needs_config.schema_definitions:
        # nothing to validate
        return

    if not isinstance(needs_config.schema_definitions, dict):
        raise NeedsConfigException("Schemas entry 'schemas' is not a dict.")

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

    # resolve $ref entries in schema; this is done before the typeguard check
    # to check the final schema structure and give feedback based on it
    if "$defs" in needs_config.schema_definitions:
        defs = needs_config.schema_definitions["$defs"]
        resolve_refs(defs, needs_config.schema_definitions, set())

    # set idx for logging purposes, it's part of the schema name
    for idx, schema in enumerate(needs_config.schema_definitions["schemas"]):
        schema["idx"] = idx

    # inject extra option types to schema, this is required before typeguard check
    # as the type field switches between the TypedDict options;
    # this improves error messages
    extra_links = {link["option"] for link in needs_config.extra_links}
    core_field_type_map = get_core_field_type_map()
    for schema in needs_config.schema_definitions["schemas"]:
        schema_name = get_schema_name(schema)
        populate_field_type(
            schema,
            schema_name,
            core_field_type_map,
            extra_option_type_map,
            extra_links,
        )

    # validate schemas against type hints at runtime
    for schema in needs_config.schema_definitions["schemas"]:
        try:
            check_type(schema, SchemasRootType)
        except TypeCheckError as exc:
            schema_name = get_schema_name(schema)
            raise NeedsConfigException(
                f"Schemas entry '{schema_name}' is not valid:\n{exc}"
            ) from exc

    # check if network links are defined as extra links
    check_network_links_against_extra_links(
        needs_config.schema_definitions["schemas"],
        extra_links,
    )

    # check severity and inject default if not set
    validate_severity(needs_config.schema_definitions["schemas"])

    # check safe regex patterns of schemas
    validate_regex_patterns_schemas(needs_config)


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


def validate_regex_patterns_extra_options(needs_config: NeedsSphinxConfig) -> None:
    """Validate regex patterns of extra options."""
    for option_name, option in needs_config.extra_options.items():
        if (
            option.schema is None
            or not option.schema
            or option.schema.get("type") != "string"
        ):
            continue
        validate_schema_patterns(option.schema, f"extra_options.{option_name}.schema")


def validate_regex_patterns_extra_links(needs_config: NeedsSphinxConfig) -> None:
    """Validate regex patterns of extra links."""

    for extra_link in needs_config.extra_links:
        if "schema" not in extra_link or extra_link["schema"] is None:
            continue

        validate_schema_patterns(
            extra_link["schema"], f"extra_links.{extra_link['option']}.schema"
        )


def validate_regex_patterns_schemas(needs_config: NeedsSphinxConfig) -> None:
    """Validate regex patterns of schemas."""
    for schema in needs_config.schema_definitions["schemas"]:
        schema_name = get_schema_name(schema)
        try:
            validate_schema_patterns(schema, f"schemas.{schema_name}")
        except NeedsConfigException as exc:
            raise NeedsConfigException(
                f"Schemas entry '{schema_name}' is not valid:\n{exc}"
            ) from exc


def validate_extra_link_schemas(needs_config: NeedsSphinxConfig) -> None:
    """Validate types of extra links in needs_config and set default."""
    for extra_link in needs_config.extra_links:
        if "schema" not in extra_link or extra_link["schema"] is None:
            continue
        try:
            check_type(extra_link["schema"], ExtraLinkSchemaType)
        except TypeCheckError as exc:
            raise NeedsConfigException(
                f"Schema for extra link '{extra_link['option']}' is not valid:\n{exc}"
            ) from exc


def inject_type_extra_link_schemas(needs_config: NeedsSphinxConfig) -> None:
    """Inject the optional type field to extra link schemas."""
    type_inject_fields = ["contains", "items"]
    for extra_link in needs_config.extra_links:
        if "schema" not in extra_link or extra_link["schema"] is None:
            continue
        for field in type_inject_fields:
            if (
                field in extra_link["schema"]
                and "type" not in extra_link["schema"][field]  # type: ignore[literal-required]
            ):
                # set string as default
                extra_link["schema"][field]["type"] = "string"  # type: ignore[literal-required]


def inject_type_and_validate_extra_option_schemas(
    needs_config: NeedsSphinxConfig,
) -> dict[str, EXTRA_OPTION_BASE_TYPES_TYPE]:
    """
    Inject missing types of extra options in needs_config and validate the config.

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
            # nothing to check, leave it at None so it is explicitly unset;
            # remember the type in case it needs to be injected to
            # needs_config.schema_definitions later
            option_type_map[option] = "string"
            continue
        if "type" not in value.schema:
            # set string as default;
            # mypy is confused because it does not infer that
            # type decides about which TypedDict applies
            value.schema["type"] = "string"  # type: ignore[arg-type]
        option_type_ = value.schema["type"]
        if option_type_ not in string_type_to_typeddict_map:
            raise NeedsConfigException(
                f"Schema for extra option '{option}' has invalid type: {option_type_}. "
                f"Allowed types are: {', '.join(string_type_to_typeddict_map.keys())}"
            )
        try:
            # below check happens late because the type system does not know that
            # the type field determines the required TypedDict which leads
            # to improved error messages
            check_type(
                value.schema,
                string_type_to_typeddict_map[option_type_],
            )
        except TypeCheckError as exc:
            raise NeedsConfigException(
                f"Schema for extra option '{option}' is not valid:\n{exc}"
            ) from exc
        option_type_map[option] = option_type_
    return option_type_map


def check_network_links_against_extra_links(
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
    # TODO(Marco): this function could be improved to run on defined types, not on Any;
    #              this would make the detection of 'properties' safer
    if isinstance(curr_item, dict):
        # looking for 'properties' is a bit dangerous
        if (
            "properties" in curr_item
            and isinstance(curr_item["properties"], dict)
            and all(isinstance(k, str) for k in curr_item["properties"])
            and all(isinstance(v, dict) for v in curr_item["properties"].values())
        ):
            if "type" not in curr_item:
                # need dictionary type
                curr_item["type"] = "object"
            for key, value in curr_item["properties"].items():
                if "type" not in value:
                    if key in extra_option_type_map:
                        value["type"] = extra_option_type_map[key]
                    elif key in extra_links:
                        value["type"] = "array"
                        if "contains" not in value:
                            value["contains"] = {"type": "string"}
                        else:
                            if "type" not in value["contains"]:
                                value["contains"]["type"] = "string"
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
                    elif key in extra_links and value["type"] != "array":
                        raise NeedsConfigException(
                            f"Config error in schema '{schema_name}': Field '{key}' has type '{value['type']}', "
                            "but expected 'array'."
                        )
                    elif (
                        key in core_field_type_map
                        and value["type"] != core_field_type_map[key]
                    ):
                        raise NeedsConfigException(
                            f"Config error in schema '{schema_name}': Field '{key}' has type '{value['type']}', "
                            f"but expected '{core_field_type_map[key]}'."
                        )
                    else:
                        # type is already set, nothing to do;
                        # mismatching types will be checked by typeguard
                        pass

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


class UnsafePatternError(ValueError):
    """Raised when a regex pattern contains unsafe constructs."""

    def __init__(self, pattern: str, reason: str) -> None:
        super().__init__(f"Unsafe regex pattern '{pattern}': {reason}")
        self.pattern: str = pattern
        self.reason: str = reason


def validate_regex_pattern(pattern: str) -> None:
    """
    Validate that a regex pattern uses only basic features for cross-platform use.

    Only allows basic regex constructs that work consistently across
    various regex engines (e.g. Python, Rust, SQLite, Kuzu).

    :param pattern: The regex pattern to validate
    :raises UnsafePatternError: If the pattern contains unsupported constructs
    """
    # First check if the pattern compiles in Python
    try:
        re.compile(pattern)
    except re.error as exc:
        raise UnsafePatternError(pattern, f"invalid regex syntax: {exc}") from exc

    # Check for specific unsafe constructs first (more precise detection)
    unsafe_constructs = {
        r"\(\?[=!<]": "lookahead/lookbehind assertions",
        r"\\[1-9]": "backreferences",
        r"\(\?[^:]": "special groups (other than non-capturing)",
        r"\\[pPdDsSwWbBAZ]": "character class shortcuts and word boundaries",
        r"\(\?\#": "comments",
        r"\\[uUxc]": "Unicode and control character escapes",
        r"\(\?\&": "subroutine calls",
        r"\(\?\+": "relative subroutine calls",
        r"\(\?\(": "conditional patterns",
        r"\(\?>": "atomic groups",
        r"[+*?]\+": "possessive quantifiers",
        r"\(\?R\)": "recursive patterns",
    }

    for construct_pattern, description in unsafe_constructs.items():
        if re.search(construct_pattern, pattern):
            raise UnsafePatternError(pattern, f"contains {description}")

    # Additional validation for nested quantifiers that could cause backtracking
    if re.search(r"\([^)]*[+*?][^)]*\)[+*?]", pattern):
        raise UnsafePatternError(
            pattern, "contains nested quantifiers that may cause backtracking"
        )

    # Define allowed basic regex constructs using allowlist approach
    allowed_pattern = r"""
    ^                           # Start of string
    (?:                         # Non-capturing group for alternatives
        [^\\()[\]{}|+*?^$]      # Literal characters (not special)
        |\\[\\()[\]{}|+*?^$nrtvfs]  # Basic escaped characters and whitespace
        |\[[^\]]*\]             # Character classes [abc], [a-z], [^abc]
        |\(\?:                  # Non-capturing groups (?:...)
        |\(                     # Capturing groups (...)
        |\)                     # Group closing
        |\|                     # Alternation
        |[+*?]                  # Basic quantifiers
        |\{[0-9]+(?:,[0-9]*)?\} # Counted quantifiers {n}, {n,}, {n,m}
        |\^                     # Start anchor
        |\$                     # End anchor
        |\.                     # Any character
    )*                          # Zero or more occurrences
    $                           # End of string
    """

    # Remove whitespace and comments from the validation pattern
    validation_regex = re.sub(r"\s+|#.*", "", allowed_pattern)

    if not re.match(validation_regex, pattern):
        raise UnsafePatternError(pattern, "contains unsupported regex construct")


def validate_schema_patterns(schema: Any, path: str = "") -> None:
    """
    Recursively validate all regex patterns in a schema.

    :param schema: The schema dictionary to validate
    :param path: Current path in the schema (for error reporting)
    :raises UnsafePatternError: If any pattern is unsafe
    """
    if isinstance(schema, dict):
        if "type" in schema and schema["type"] == "string" and "pattern" in schema:
            try:
                validate_regex_pattern(schema["pattern"])
            except UnsafePatternError as exc:
                raise NeedsConfigException(
                    f"Unsafe pattern '{exc.pattern}' at '{path}': {exc.reason}"
                ) from exc
        for key, value in schema.items():
            current_path = f"{path}.{key}" if path else key
            if isinstance(value, dict):
                validate_schema_patterns(value, current_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    item_path = f"{current_path}[{i}]"
                    if isinstance(item, dict):
                        validate_schema_patterns(item, item_path)
    elif isinstance(schema, list):
        for i, item in enumerate(schema):
            current_path = f"{path}[{i}]" if path else f"[{i}]"
            if isinstance(item, dict | list):
                validate_schema_patterns(item, current_path)
