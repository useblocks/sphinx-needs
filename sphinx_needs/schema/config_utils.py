"""Utilities for schemas in Sphinx Needs configuration (mainly validate)."""

from __future__ import annotations

import re
from typing import Any, Literal, cast

from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from typeguard import TypeCheckError, check_type

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs.logging import get_logger
from sphinx_needs.needs_schema import FieldsSchema
from sphinx_needs.schema.config import (
    EXTRA_OPTION_BASE_TYPES_STR,
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

log = get_logger(__name__)


def has_any_global_extra_schema_defined(needs_config: NeedsSphinxConfig) -> bool:
    """
    Check if any extra option or extra link has a schema defined.

    :return: True if any extra option or extra link has a schema set, False otherwise.
    """
    # Check extra options
    for option_value in needs_config.extra_options.values():
        if option_value.schema is not None:
            return True

    # Check extra links
    for extra_link in needs_config.extra_links:
        if "schema" in extra_link and extra_link["schema"] is not None:
            return True

    return False


def validate_schemas_config(needs_config: NeedsSphinxConfig) -> None:
    """Check basics in extra option and extra link schemas."""

    validate_extra_option_schemas(needs_config)

    inject_type_extra_link_schemas(needs_config)
    validate_extra_link_schemas(needs_config)

    # check for disallowed regex patterns
    validate_regex_patterns_extra_options(needs_config)
    validate_regex_patterns_extra_links(needs_config)

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

    # resolve $ref entries in schema; this is done before the typeguard check
    # to check the final schema structure and give feedback based on it
    if "$defs" in needs_config.schema_definitions:
        defs = needs_config.schema_definitions["$defs"]
        resolve_refs(defs, needs_config.schema_definitions, set())

    # set idx for logging purposes, it's part of the schema name
    for idx, schema in enumerate(needs_config.schema_definitions["schemas"]):
        schema["idx"] = idx

    # check severity and inject default if not set
    validate_severity(needs_config.schema_definitions["schemas"])


def resolve_schemas_config(
    app: Sphinx, env: BuildEnvironment, _docnames: list[str]
) -> None:
    """
    Validates schema definitions and inject type information.

    Invokes the typeguard library to re-use existing type hints.
    Mostly checking for TypedDicts.
    """
    needs_config = NeedsSphinxConfig(app.config)

    if not (
        needs_config.schema_definitions
        and "schemas" in needs_config.schema_definitions
        and needs_config.schema_definitions["schemas"]
    ):
        return

    fields_schema = SphinxNeedsData(env).get_schema()

    # inject extra/link/core option types to each nested schema, to avoid silent json schema
    # failures; this must happens before the typeguard check because it requires type fields
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
            check_type(schema, SchemasRootType)
        except TypeCheckError as exc:
            schema_name = get_schema_name(schema)
            raise NeedsConfigException(
                f"Schemas entry '{schema_name}' is not valid:\n{exc}"
            ) from exc

    # after typeguard check, we can safely walk the schema for nested checks;
    # check if network links are defined as extra links
    check_network_links_against_extra_links(
        needs_config.schema_definitions["schemas"],
        fields_schema,
    )

    # check safe regex patterns of schemas
    validate_regex_patterns_schemas(needs_config)


def get_schema_name(schema: SchemasRootType) -> str:
    """Get a human-readable name for the schema considering its optional id and list index."""
    schema_id = schema.get("id")
    idx = schema["idx"]
    schema_name = f"{schema_id}[{idx}]" if schema_id else f"[{idx}]"
    return schema_name


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
        if option.schema is None or option.schema["type"] != "string":
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
    if "schemas" not in needs_config.schema_definitions:
        return
    for schema in needs_config.schema_definitions["schemas"]:
        schema_name = get_schema_name(schema)
        try:
            validate_schema_patterns(schema, f"schemas.{schema_name}")
        except NeedsConfigException as exc:
            raise NeedsConfigException(
                f"Schemas entry '{schema_name}' is not valid:\n{exc}"
            ) from exc


def inject_type_extra_link_schemas(needs_config: NeedsSphinxConfig) -> None:
    """Inject the optional type field to extra link schemas."""

    for extra_link in needs_config.extra_links:
        if "schema" not in extra_link or extra_link["schema"] is None:
            continue
        if "type" not in extra_link["schema"]:
            extra_link["schema"]["type"] = "array"
        type_inject_fields = ["contains", "items"]
        for field in type_inject_fields:
            if (
                field in extra_link["schema"]
                and "type" not in extra_link["schema"][field]  # type: ignore[literal-required]
            ):
                # set string as default
                extra_link["schema"][field]["type"] = "string"  # type: ignore[literal-required]


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
        if "contains" not in extra_link["schema"]:
            contains_deps = {"minContains", "maxContains"}
            for field in contains_deps:
                if field in extra_link["schema"]:
                    raise NeedsConfigException(
                        f"Schema for extra link '{extra_link['option']}' has '{field}' defined, "
                        "but 'contains' is missing."
                    )


def validate_extra_option_schemas(
    needs_config: NeedsSphinxConfig,
) -> None:
    """
    Check user provided extra options.

    :return: Map of extra option names to their types as strings.
    """
    string_type_to_typeddict_map = {
        "string": ExtraOptionStringSchemaType,
        "boolean": ExtraOptionBooleanSchemaType,
        "integer": ExtraOptionIntegerSchemaType,
        "number": ExtraOptionNumberSchemaType,
        "array": ExtraOptionMultiValueSchemaType,
    }
    # iterate over all extra options from config and API;
    # API needs to make sure to run earlier (see priority) if options are added
    for option, value in needs_config.extra_options.items():
        if value.schema is None:
            # nothing to check, leave it at None so it is explicitly unset
            continue
        if "type" not in value.schema:
            raise NeedsConfigException(
                f"Schema for extra option '{option}' does not define a type."
            )
        option_type_ = value.schema["type"]
        if option_type_ not in string_type_to_typeddict_map:
            raise NeedsConfigException(
                f"Schema for extra option '{option}' has invalid type: {option_type_}. "
                f"Allowed types are: {', '.join(string_type_to_typeddict_map.keys())}"
            )

        try:
            # this also checks array items / contains types
            check_type(
                value.schema,
                string_type_to_typeddict_map[option_type_],
            )
        except TypeCheckError as exc:
            raise NeedsConfigException(
                f"Schema for extra option '{option}' is not valid:\n{exc}"
            ) from exc

        if (
            option_type_ == "array"
            and "items" in value.schema
            and "contains" in value.schema
        ):
            # if the option contains both items and contains, the types must be identical
            # the type field must exist after the typeguard check
            items_type = value.schema["items"]["type"]  # type: ignore[typeddict-item]
            contains_type = value.schema["contains"]["type"]  # type: ignore[typeddict-item]
            if items_type != contains_type:
                raise NeedsConfigException(
                    f"Schema for extra option '{option}' has both 'items' and 'contains' defined, "
                    f"but their types do not match: items.type={items_type}, contains.type={contains_type}."
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
    curr_item: Any,
    schema_name: str,
    fields_schema: FieldsSchema,
    path: str = "",
) -> None:
    """
    Inject field type into select / validate fields in schema.

    If a schema is defined on extra options, the type fields is
    required. It is the primary type information for the field.
    The JSON schema definition may also contain the type (NotRequired)
    but it must match the extra option type. If it is not given, it
    is injected by this function.

    Users might not be aware that schema validation will not complain if e.g.
    a minimium is set for an integer, but the type is not. JSON schema
    validators only complain if the type matches to the constraint.

    If the field is of type extra option but no type is defined, string is assumed.
    For link field types, an array of strings is the only possible value.
    Due to this, it is NotRequired for extra link schema configuration.

    :param curr_item: The current schema item being processed
    :param schema_name: The name/identifier of the root schema
    :param fields_schema: The fields schema containing field definitions
    :param path: The current path in the schema hierarchy for error reporting
    """
    # TODO(Marco): this function could be improved to run on defined types, not on Any;
    #              this would make the detection of 'array' or 'object' safer;
    #              however, typeguard looks over the final schema anyway
    if isinstance(curr_item, dict):
        # set 'object' type
        keys_indicating_object = {"properties", "required", "unevaluatedProperties"}
        found_keys_object = [key for key in keys_indicating_object if key in curr_item]
        if found_keys_object:
            if "type" not in curr_item:
                curr_item["type"] = "object"
            else:
                if curr_item["type"] != "object":
                    raise NeedsConfigException(
                        f"Config error in schema '{schema_name}' at path '{path}': "
                        f"Item has keys {found_keys_object}, but type is '{curr_item['type']}', "
                        f"expected 'object'."
                    )
        keys_indicating_array = {
            "items",
            "contains",
            "minItems",
            "maxItems",
            "minContains",
            "maxContains",
        }
        found_keys_array = [key for key in keys_indicating_array if key in curr_item]
        if any(key in curr_item for key in keys_indicating_array):
            if "type" not in curr_item:
                curr_item["type"] = "array"
            else:
                if curr_item["type"] != "array":
                    raise NeedsConfigException(
                        f"Config error in schema '{schema_name}' at path '{path}': "
                        f"Item has keys {found_keys_array}, but type is '{curr_item['type']}', "
                        f"expected 'array'."
                    )
        found_properties_or_all_of = False
        if (
            "properties" in curr_item
            and isinstance(curr_item["properties"], dict)
            and all(isinstance(k, str) for k in curr_item["properties"])
            and all(isinstance(v, dict) for v in curr_item["properties"].values())
        ):
            found_properties_or_all_of = True
            properties_path = f"{path}.properties" if path else "properties"

            for key, value in curr_item["properties"].items():
                field_path = f"{properties_path}.{key}"

                if fields_schema.get_extra_field(key) is not None:
                    extra_field = fields_schema.get_extra_field(key)
                    assert extra_field is not None  # Type narrowing for pylance
                    if "type" not in value:
                        value["type"] = extra_field.type
                    else:
                        if value["type"] != extra_field.type:
                            raise NeedsConfigException(
                                f"Config error in schema '{schema_name}' at path '{field_path}': "
                                f"Field '{key}' has type '{value['type']}', but expected '{extra_field.type}'."
                            )
                    if extra_field.type == "array":
                        container_fields = ["items", "contains"]
                        for container_field in container_fields:
                            if container_field in value:
                                container_path = f"{field_path}.{container_field}"
                                if "type" not in value[container_field]:
                                    value[container_field]["type"] = (
                                        extra_field.item_type
                                    )
                                else:
                                    if (
                                        value[container_field]["type"]
                                        != extra_field.item_type
                                    ):
                                        raise NeedsConfigException(
                                            f"Config error in schema '{schema_name}' at path '{container_path}': "
                                            f"Field '{key}' has {container_field}.type '{value[container_field]['type']}', "
                                            f"but expected '{extra_field.item_type}'."
                                        )
                elif fields_schema.get_link_field(key) is not None:
                    link_field = fields_schema.get_link_field(key)
                    assert link_field is not None  # Type narrowing for pylance
                    if "type" not in value:
                        value["type"] = "array"
                    else:
                        if value["type"] != "array":
                            raise NeedsConfigException(
                                f"Config error in schema '{schema_name}' at path '{field_path}': "
                                f"Field '{key}' has type '{value['type']}', but expected 'array'."
                            )
                    container_fields = ["items", "contains"]
                    for container_field in container_fields:
                        if container_field in value:
                            container_path = f"{field_path}.{container_field}"
                            if "type" not in value[container_field]:
                                value[container_field]["type"] = "string"
                            else:
                                if value[container_field]["type"] != "string":
                                    raise NeedsConfigException(
                                        f"Config error in schema '{schema_name}' at path '{container_path}': "
                                        f"Field '{key}' has {container_field}.type '{value[container_field]['type']}', "
                                        f"but expected 'string'."
                                    )
                else:
                    # first try to resolve from FieldsSchema
                    core_field = fields_schema.get_core_field(key)
                    if core_field is not None:
                        _type = core_field.type
                        _item_type = core_field.item_type
                    else:
                        # no success, look in NeedsCoreFields
                        core_field_result = get_core_field_type(key)
                        if core_field_result is None:
                            # field is unknown
                            raise NeedsConfigException(
                                f"Config error in schema '{schema_name}' at path '{field_path}': "
                                f"Field '{key}' is not a known extra option, extra link, or core field."
                            )
                        _type, _item_type = core_field_result
                    if "type" not in value:
                        value["type"] = _type
                    else:
                        if value["type"] != _type:
                            raise NeedsConfigException(
                                f"Config error in schema '{schema_name}' at path '{field_path}': "
                                f"Field '{key}' has type '{value['type']}', but expected '{_type}'."
                            )
                    if _type == "array":
                        container_fields = ["items", "contains"]
                        for container_field in container_fields:
                            if container_field in value:
                                container_path = f"{field_path}.{container_field}"
                                if "type" not in value[container_field]:
                                    value[container_field]["type"] = _item_type
                                else:
                                    if value[container_field]["type"] != _item_type:
                                        raise NeedsConfigException(
                                            f"Config error in schema '{schema_name}' at path '{container_path}': "
                                            f"Field '{key}' has {container_field}.type '{value[container_field]['type']}', "
                                            f"but expected '{_item_type}'."
                                        )
        if "allOf" in curr_item and isinstance(curr_item["allOf"], list):
            found_properties_or_all_of = True
            for index, value in enumerate(curr_item["allOf"]):
                all_of_path = f"{path}.allOf[{index}]" if path else f"allOf[{index}]"
                populate_field_type(value, schema_name, fields_schema, all_of_path)
        if not found_properties_or_all_of:
            # iterate deeper
            for key, value in curr_item.items():
                current_path = f"{path}.{key}" if path else key
                populate_field_type(value, schema_name, fields_schema, current_path)
    elif isinstance(curr_item, list):
        for index, value in enumerate(curr_item):
            current_path = f"{path}[{index}]" if path else f"[{index}]"
            populate_field_type(value, schema_name, fields_schema, current_path)


def get_core_field_type(
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
        if non_null_type in EXTRA_OPTION_BASE_TYPES_STR:
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
