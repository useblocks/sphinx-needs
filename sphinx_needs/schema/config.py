"""
Types and violations for schema validation.

There are 3 places the types are used:
1. In the extra option and extra links definition.
2. For the JSON schema coming from schema_definitions and schema_definitions_from_json configs.
3. For runtime type checking of the loaded JSON schema config.

All below types have the field 'type' set as required field.
For case 1. this is important, as it is the primar type information source and users *have* to
provide it.
For 2. and 3. it is not required. If it is not given, it is injected before the type check
occurs. If it is given, the types have to match what is provided in 1.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from enum import Enum, IntEnum
from functools import cache
from pathlib import Path
from typing import Any, Final, Literal, TypedDict, cast

import jsonschema_rs
from typing_extensions import NotRequired

EXTRA_OPTION_BASE_TYPES_STR: Final[set[str]] = {
    "string",
    "integer",
    "number",
    "boolean",
    "array",
}
"""Extra option base types as string that are supported in the schemas."""

EXTRA_OPTION_BASE_TYPES_TYPE = Literal[
    "string", "integer", "number", "boolean", "array"
]
"""Extra option base types as types that are supported in the schemas."""

MAX_NESTED_NETWORK_VALIDATION_LEVELS: Final[int] = 4
"""Maximum number of nested network validation levels."""


@cache
def _get_schema(klass: type) -> jsonschema_rs.Validator:
    """Get the JSON schema for the given TypedDict class."""
    content = json.loads(
        Path(__file__)
        .parent.joinpath("jsons", f"{klass.__name__}.schema.json")
        .read_text()
    )
    return jsonschema_rs.validator_for(content)


class ExtraOptionStringSchemaType(TypedDict):
    """String extra option schema."""

    type: Literal["string"]
    """Extra option string type."""
    minLength: NotRequired[int]
    """Minimum length of the string."""
    maxLength: NotRequired[int]
    """Maximum length of the string."""
    pattern: NotRequired[str]
    """A regex pattern to validate against."""
    format: NotRequired[
        Literal[
            "date-time",
            "date",
            "time",
            "duration",
            "email",
            "uri",
            "uuid",
        ]
    ]
    """A format string to validate against, e.g. 'date-time'."""
    enum: NotRequired[list[str]]
    """A list of allowed values for the string."""
    const: NotRequired[str]
    """A constant value that the string must match."""


def validate_extra_option_string_schema(data: Any) -> ExtraOptionStringSchemaType:
    """Validate that the given data is an ExtraOptionStringSchemaType.

    :raises TypeError: if the data is not valid.
    """
    schema = _get_schema(ExtraOptionStringSchemaType)
    try:
        schema.validate(data)
    except jsonschema_rs.ValidationError as e:
        raise TypeError(str(e)) from e
    return cast(ExtraOptionStringSchemaType, data)


class ExtraOptionNumberSchemaType(TypedDict):
    """
    Float extra option schema.

    Python reads in JSON numbers as floats. The jsonschema library
    handles precision issues with floats using a tolerance-based approach.
    """

    type: Literal["number"]
    """Extra option integer type."""
    minimum: NotRequired[float]
    """Minimum value."""
    exclusiveMinimum: NotRequired[float]
    """Exclusive minimum value."""
    maximum: NotRequired[float]
    """Maximum value."""
    exclusiveMaximum: NotRequired[float]
    """Exclusive maximum value."""
    multipleOf: NotRequired[float]
    """Restriction to multiple of a given number, must be positive."""
    enum: NotRequired[list[float]]
    """A list of allowed values."""
    const: NotRequired[float]
    """A constant value that the number must match."""


def validate_extra_option_number_schema(data: Any) -> ExtraOptionNumberSchemaType:
    """Validate that the given data is an ExtraOptionNumberSchemaType.

    :raises TypeError: if the data is not valid.
    """
    schema = _get_schema(ExtraOptionNumberSchemaType)
    try:
        schema.validate(data)
    except jsonschema_rs.ValidationError as e:
        raise TypeError(str(e)) from e
    return cast(ExtraOptionNumberSchemaType, data)


class ExtraOptionIntegerSchemaType(TypedDict):
    """Integer extra option schema."""

    type: Literal["integer"]
    """Extra option integer type."""
    minimum: NotRequired[int]
    """Minimum value."""
    exclusiveMinimum: NotRequired[int]
    """Exclusive minimum value."""
    maximum: NotRequired[int]
    """Maximum value."""
    exclusiveMaximum: NotRequired[int]
    """Exclusive maximum value."""
    multipleOf: NotRequired[int]
    """Restriction to multiple of a given integer, must be positive."""
    enum: NotRequired[list[int]]
    """A list of allowed values."""
    const: NotRequired[int]
    """A constant value that the integer must match."""


def validate_extra_option_integer_schema(data: Any) -> ExtraOptionIntegerSchemaType:
    """Validate that the given data is an ExtraOptionIntegerSchemaType.

    :raises TypeError: if the data is not valid.
    """
    schema = _get_schema(ExtraOptionIntegerSchemaType)
    try:
        schema.validate(data)
    except jsonschema_rs.ValidationError as e:
        raise TypeError(str(e)) from e
    return cast(ExtraOptionIntegerSchemaType, data)


class ExtraOptionBooleanSchemaType(TypedDict):
    """
    Boolean extra option schema.

    A predefined set of truthy/falsy strings are accepted:
    - truthy = {"true", "yes", "y", "on", "1"}
    - falsy = {"false", "no", "n", "off", "0"}

    For fixed values, the const field can be used.
    enum is not supported as const is functionally equivalent and less verbose.
    """

    type: Literal["boolean"]
    """Extra option boolean type."""
    const: NotRequired[bool]
    """A constant value that the integer must match."""


def validate_extra_option_boolean_schema(data: Any) -> ExtraOptionBooleanSchemaType:
    """Validate that the given data is an ExtraOptionBooleanSchemaType.

    :raises TypeError: if the data is not valid.
    """
    schema = _get_schema(ExtraOptionBooleanSchemaType)
    try:
        schema.validate(data)
    except jsonschema_rs.ValidationError as e:
        raise TypeError(str(e)) from e
    return cast(ExtraOptionBooleanSchemaType, data)


RefItemType = TypedDict(
    "RefItemType",
    {
        "$ref": str,
    },
)

SchemaVersionType = TypedDict(
    "SchemaVersionType",
    {
        "$schema": NotRequired[str],
    },
)


class AllOfSchemaType(TypedDict):
    allOf: NotRequired[list[RefItemType | NeedFieldsSchemaType]]


ExtraOptionBaseSchemaTypes = (
    ExtraOptionStringSchemaType
    | ExtraOptionBooleanSchemaType
    | ExtraOptionIntegerSchemaType
    | ExtraOptionNumberSchemaType
)
"""Union type for all single value extra option schemas."""


class ExtraOptionMultiValueSchemaType(TypedDict):
    """
    Multi value extra option such as a list of strings, integers, numbers, or booleans.

    Current SN use case are tags.
    """

    type: Literal["array"]
    """Multi value extra option such as a list of strings, integers, numbers, or booleans."""
    items: ExtraOptionBaseSchemaTypes
    """Schema constraints for all items."""
    minItems: NotRequired[int]
    """Minimum number of items in the array."""
    maxItems: NotRequired[int]
    """Maximum number of items in the array."""
    contains: NotRequired[ExtraOptionBaseSchemaTypes]
    """Schema constraints for some items."""
    minContains: NotRequired[int]
    """Minimum number of contains items in the array."""
    maxContains: NotRequired[int]
    """Maximum number of contains items in the array."""
    uniqueItems: NotRequired[bool]
    """Whether all items in the array must be unique."""


def validate_extra_option_multi_value_schema(
    data: Any,
) -> ExtraOptionMultiValueSchemaType:
    """Validate that the given data is an ExtraOptionMultiValueSchemaType.

    :raises TypeError: if the data is not valid.
    """
    schema = _get_schema(ExtraOptionMultiValueSchemaType)
    try:
        schema.validate(data)
    except jsonschema_rs.ValidationError as e:
        raise TypeError(str(e)) from e
    if "contains" in data and "items" in data:
        # if the option contains both items and contains, the types must be identical
        items_type = data["items"]["type"]
        contains_type = data["contains"]["type"]
        if items_type != contains_type:
            raise TypeError(
                f"'items' type '{items_type}' and 'contains' type '{contains_type}' must be identical."
            )
    return cast(ExtraOptionMultiValueSchemaType, data)


ExtraOptionSchemaTypes = ExtraOptionBaseSchemaTypes | ExtraOptionMultiValueSchemaType
"""Union type for all extra option schemas, including multi-value options."""


_OPTION_VALIDATORS: Final[Mapping[str, Callable[[Any], ExtraOptionSchemaTypes]]] = {
    "string": validate_extra_option_string_schema,
    "boolean": validate_extra_option_boolean_schema,
    "integer": validate_extra_option_integer_schema,
    "number": validate_extra_option_number_schema,
    "array": validate_extra_option_multi_value_schema,
}


def validate_extra_option_schema(data: Any) -> ExtraOptionSchemaTypes:
    """Validate that the given data is an ExtraOptionBaseSchemaTypes.

    :raises TypeError: if the data is not valid.
    """
    if not isinstance(data, dict):
        raise TypeError("Must be a dict.")
    if "type" not in data:
        raise TypeError("Must have a 'type' field.")
    type_ = data["type"]
    if type_ not in EXTRA_OPTION_BASE_TYPES_STR:
        raise TypeError(
            f"Extra option schema has invalid type '{type_}'. "
            f"Must be one of {sorted(EXTRA_OPTION_BASE_TYPES_STR)}."
        )
    validator = _OPTION_VALIDATORS[type_]
    return validator(data)


class ExtraLinkItemSchemaType(TypedDict):
    """Items in array of link string ids"""

    type: Literal["string"]
    """Extra link string type, can only be string and is injected automatically."""
    minLength: NotRequired[int]
    """Minimum string length of each outgoing link id."""
    maxLength: NotRequired[int]
    """Maximum string length of each outgoing link id."""
    pattern: NotRequired[str]
    """A regex pattern to validate against."""


class ExtraLinkSchemaType(TypedDict):
    """Defines a schema for unresolved need extra string links."""

    type: Literal["array"]
    """Type for extra links, can only be array and is injected automatically."""
    items: NotRequired[ExtraLinkItemSchemaType]
    """Schema constraints that applies to all items in the need id string list."""
    minItems: NotRequired[int]
    """Minimum number of items in the array (outgoing link ids)."""
    maxItems: NotRequired[int]
    """Maximum number of items in the array (outgoing link ids)."""
    contains: NotRequired[ExtraLinkItemSchemaType]
    """Schema constraints that must be contained in the need id string list."""
    minContains: NotRequired[int]
    """Minimum number of contains items in the array (outgoing link ids)."""
    maxContains: NotRequired[int]
    """Maximum number of contains items in the array (outgoing link ids)."""


def validate_extra_link_schema_type(data: Any) -> ExtraLinkSchemaType:
    """Validate that the given data is an ExtraLinkSchemaType.

    :raises TypeError: if the data is not valid.
    """
    schema = _get_schema(ExtraLinkSchemaType)
    try:
        schema.validate(data)
    except jsonschema_rs.ValidationError as e:
        raise TypeError(str(e)) from e
    if "contains" not in data:
        for field in ("minContains", "maxContains"):
            if field in data:
                raise TypeError(f"'{field}' defined, but 'contains' is missing.")
    return cast(ExtraLinkSchemaType, data)


ExtraOptionAndLinkSchemaTypes = ExtraOptionSchemaTypes | ExtraLinkSchemaType
"""Union type for all extra option and link schemas."""


class NeedFieldsSchemaType(AllOfSchemaType):
    """
    Schema for a set of need fields of all schema types.

    This includes single value extra options, multi-value extra options,
    and unresolved extra links.

    Intented to validate multiple fields on a need type.
    """

    type: NotRequired[Literal["object"]]
    """All fields of a need stored in a dict (not required because it's the default)."""
    properties: NotRequired[dict[str, ExtraOptionAndLinkSchemaTypes]]
    required: NotRequired[list[str]]
    """List of required fields in the need."""
    unevaluatedProperties: NotRequired[bool]


class NeedFieldsSchemaWithVersionType(NeedFieldsSchemaType, SchemaVersionType):
    """Schema for a set of need fields with schema version."""


class MessageRuleEnum(str, Enum):
    """All known rules for debugging and validation warnings."""

    cfg_schema_error = "cfg_schema_error"
    """The user provided schema is invalid."""
    option_success = "option_success"
    """Global extra option validation was successful."""
    option_fail = "option_fail"
    """Global extra option validation failed."""
    extra_link_success = "extra_link_success"
    """Global extra link validation was successful."""
    extra_link_fail = "extra_link_fail"
    """Global extra link validation failed."""
    select_success = "select_success"
    """
    Need validates against the select schema.

    This is not an error, but used for debugging."""
    select_fail = "select_fail"
    """
    Need does not validate against the select schema
    
    This is not an error, but used for debugging.
    """
    local_success = "local_success"
    """
    Need local validation was successful.
    
    This is not an error, but used for debugging.
    """
    local_fail = "local_fail"
    """Need local validation failed."""
    network_missing_target = "network_missing_target"
    """An outgoing link target cannot be resolved."""
    network_contains_too_few = "network_contains_too_few"
    """minContains validation failed for the given link_schema link type."""
    network_contains_too_many = "network_contains_too_many"
    """maxContains validation failed for the given link_schema link type."""
    network_items_fail = "network_item_fail"
    """Need does not validate against the network item schema."""
    network_local_success = "network_local_success"
    """
    Need validates against the local schema in a network context.

    This is like local_success but not on root level.
    This is not an error, but used for debugging.
    """
    network_local_fail = "network_local_fail"
    """
    Need does not validate against the local schema in a network context.

    This is like local_fail but not on root level.
    Users are interested why linked needs failed validation.
    """
    network_max_nest_level = "network_max_nest_level"
    """
    Maximum number of nested network validation levels reached.
    """


class SeverityEnum(IntEnum):
    """
    Severity levels for the validation messages.

    The levels are derived from the SHACL specification.
    See https://www.w3.org/TR/shacl/#severity

    config_error are user configuration errors.
    """

    none = 0
    """Succeess / no severity, used for reporting (e.g. why was no error detected)."""
    info = 1
    """Lowest severity level, used for informational messages."""
    warning = 2
    """Medium severity level."""
    violation = 3
    """Highest severity level."""
    config_error = 4
    """
    Runtime detected schema config error.

    Any error of this kind should be moved to the config-inited phase so users
    get notified early about config issues.
    See config_utils.validate_schemas_config().
    Config errors are always reported to the user.
    """


USER_CONFIG_SCHEMA_SEVERITIES = [
    SeverityEnum.info,
    SeverityEnum.warning,
    SeverityEnum.violation,
]
"""
Severity levels that can be set in the user provided schemas and for the schema_severity config."""

MAP_RULE_DEFAULT_SEVERITY: Final[dict[MessageRuleEnum, SeverityEnum]] = {
    MessageRuleEnum.cfg_schema_error: SeverityEnum.config_error,
    MessageRuleEnum.option_success: SeverityEnum.none,
    MessageRuleEnum.option_fail: SeverityEnum.violation,  # cannot be changed by user
    MessageRuleEnum.extra_link_success: SeverityEnum.none,
    MessageRuleEnum.extra_link_fail: SeverityEnum.violation,  # cannot be changed by user
    MessageRuleEnum.select_success: SeverityEnum.none,
    MessageRuleEnum.select_fail: SeverityEnum.none,
    MessageRuleEnum.local_success: SeverityEnum.none,
    MessageRuleEnum.local_fail: SeverityEnum.violation,
    MessageRuleEnum.network_missing_target: SeverityEnum.violation,
    MessageRuleEnum.network_contains_too_few: SeverityEnum.violation,
    MessageRuleEnum.network_contains_too_many: SeverityEnum.violation,
    # network local success/fail may or may not be of severity,
    # depending on the min/max specification for the link type
    # the severity is set to violation to bubble up the validations
    MessageRuleEnum.network_local_success: SeverityEnum.none,  # prevent it from bubbling up
    MessageRuleEnum.network_local_fail: SeverityEnum.violation,  # severity is handled on root schema
    MessageRuleEnum.network_max_nest_level: SeverityEnum.violation,
}
"""
Default severity for each rule.

User provided schemas can overwrite the severity of a rule.
The rules ``extra_option_fail`` and ``extra_link_fail`` cannot be changed by the user,
but they can be suppressed specifically using suppress_warnings config.
"""


class ResolvedLinkSchemaType(TypedDict, total=True):
    """
    Schema for resolved links between needs.

    Does not have a select field as the link itself is the selection.
    There are no minItems/maxItems fields as they constrain the list length.
    That should be done in the local schema as it does not require the resolution
    of the linked needs.
    """

    type: Literal["array"]
    """Resolved needs list, can only be array and is injected automatically."""
    items: NotRequired[ValidateSchemaType]
    """Schema applied to all resolved linked needs."""
    contains: NotRequired[ValidateSchemaType]
    """Schema applied to one or more resolved linked needs."""
    minContains: NotRequired[int]
    """Minimum number of items that validate against the contains schema."""
    maxContains: NotRequired[int]
    """Maximum number of items that validate against the contains schema."""


class ValidateSchemaType(TypedDict):
    """
    Validation, can either be need-local or network (requires resolving all need links).

    For network, graph traversal is possible if network is selected again.
    """

    local: NotRequired[RefItemType | AllOfSchemaType | NeedFieldsSchemaType]
    network: NotRequired[dict[str, ResolvedLinkSchemaType]]


class SchemasRootType(TypedDict):
    idx: int
    """Computed index in schemas list for logging."""
    id: NotRequired[str]
    """String id of the schema entry, used for logging."""
    severity: Literal["violation", "warning", "info"]
    """Severity of the schema, defaults to violation. Injected if not given."""
    message: NotRequired[str]
    """Custom message to be shown in case of validation errors."""
    select: NotRequired[RefItemType | AllOfSchemaType | NeedFieldsSchemaType]
    """Schema that selects the need type to which this schema applies."""
    validate: ValidateSchemaType
    """
    Validation schema for the selected needs.

    Can be either a need-local schema or a network schema that requires resolving all need links
    before validating.
    """


def validate_schemas_root_type(data: Any) -> SchemasRootType:
    """Validate that the given data is a SchemasRootType.

    :raises TypeError: if the data is not valid.
    """
    schema = _get_schema(SchemasRootType)
    try:
        schema.validate(data)
    except jsonschema_rs.ValidationError as e:
        raise TypeError(str(e)) from e
    return cast(SchemasRootType, data)


def get_schema_name(schema: SchemasRootType) -> str:
    """Get a human-readable name for the schema considering its optional id and list index."""
    schema_id = schema.get("id")
    idx = schema["idx"]
    schema_name = f"{schema_id}[{idx}]" if schema_id else f"[{idx}]"
    return schema_name


SchemasFileRootType = TypedDict(
    "SchemasFileRootType",
    {
        "$defs": NotRequired[
            dict[
                str,
                AllOfSchemaType | NeedFieldsSchemaType | ExtraOptionAndLinkSchemaTypes,
            ]
        ],
        "schemas": NotRequired[list[SchemasRootType]],
    },
)
"""schemas.json root type."""
