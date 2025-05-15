from enum import Enum, IntEnum
from typing import Any, Final, Optional, TypedDict, Union

DISALLOWED_SCHEMA_KEYS = {
    "if",
    "then",
    "else",
    "dependentSchemas",
    "dependentRequired",
    "anyOf",
    "oneOf",
    "not",
}
"""Keys that are not allowed in the user provided schemas."""


def check_schema_for_disallowed_keys(
    schema: dict[str, Any], path: str = ""
) -> list[str]:
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


class MessageRuleEnum(str, Enum):
    """All known rules for debugging and validation warnings."""

    cfg_disallowed_keys = "cfg_disallowed_keys"
    """Schema has one of the keys listed in DISALLOWED_SCHEMA_KEYS."""
    cfg_schema_error = "cfg_schema_error"
    """The user provided schema is invalid."""
    option_type_error = "option_type_error"
    """A need extra option cannot be coerced to the type specified in the schema."""
    skipped_dependency = "skipped_dependency"
    """A schema was skipped because it is has the dependency bit set."""
    skipped_wrong_type = "skipped_wrong_type"
    """
    A schema was skipped for primary validation because the need type does not match.

    This is not an error.
    """
    too_few_links = "too_few_links"
    """minItems validation failed for the given link_schema link type."""
    too_many_links = "too_many_links"
    """maxItems validation failed for the given link_schema link type."""
    unevaluated_additional_links = "unevaluated_additional_links"
    """
    Disallowed additional links were found for the given link type.

    This means at least one schema validation failed for the link type.
    """
    validation_success = "validation_success"
    """Need schema validation was successful."""
    validation_fail = "validation_fail"
    """Need schema validation failed."""
    wrong_type = "wrong_type"
    """The need type does not match the schema type in a trigger context."""
    missing_target = "missing_target"
    """An outgoing link target cannot be resolved."""


class SeverityEnum(IntEnum):
    """
    Severity levels for the validation messages.

    The levels are derived from the SHACL specification.
    See https://www.w3.org/TR/shacl/#severity

    config_error are user configuration errors.
    """

    none = 0
    info = 1
    warning = 2
    violation = 3
    config_error = 4


USER_CONFIG_SCHEMA_SEVERITIES = [
    SeverityEnum.info,
    SeverityEnum.warning,
    SeverityEnum.violation,
]
MAP_RULE_SEVERITY: Final[dict[MessageRuleEnum, SeverityEnum]] = {
    MessageRuleEnum.cfg_disallowed_keys: SeverityEnum.config_error,
    MessageRuleEnum.cfg_schema_error: SeverityEnum.config_error,
    MessageRuleEnum.option_type_error: SeverityEnum.violation,
    MessageRuleEnum.skipped_dependency: SeverityEnum.none,
    MessageRuleEnum.skipped_wrong_type: SeverityEnum.none,
    MessageRuleEnum.too_few_links: SeverityEnum.violation,
    MessageRuleEnum.too_many_links: SeverityEnum.violation,
    MessageRuleEnum.unevaluated_additional_links: SeverityEnum.violation,
    MessageRuleEnum.validation_fail: SeverityEnum.violation,
    MessageRuleEnum.validation_success: SeverityEnum.none,
    MessageRuleEnum.wrong_type: SeverityEnum.violation,
    MessageRuleEnum.missing_target: SeverityEnum.violation,
}
"""
Severity for each rule.

validation_fail can be overwritten by a severity field in the schema types list.
"""


class LinkSchemaType(TypedDict, total=True):
    """Options for links between needs"""

    schema_id: str
    """ID of the schema to be used for validation."""
    minItems: int
    """Minimum number of items in the link that validate against schema or schema_id."""
    maxItems: int
    """Maximum number of items in the link that validate against schema or schema_id."""
    unevaluatedItems: bool
    """If True, only items that validate against schema or schema_id can be part of the link type."""


class SchemaType(TypedDict, total=False):
    """Options for links between needs"""

    id: str
    """ID of the schema for referencing and logging."""
    idx: int
    """
    Index of the schema in the list of schemas.

    This is set programmatically and is used for debugging purposes.
    """
    severity: str
    """Severity level of the schema (SeverityEnum)."""
    message: str
    """Message to be shown in the validation report."""
    types: list[str]
    """List of need types that this schema applies to."""
    local_schema: dict[str, Any]
    """JSON schema to validate against if type fits and trigger is active."""
    trigger_schema: dict[str, Any]
    """Trigger JSON schema that needs to pass to activate local_schema."""
    trigger_schema_id: str
    """ID of the type schema that needs to pass to activate local_schema."""
    link_schema: dict[str, LinkSchemaType]
    """Map of link specification to link type."""
    dependency: bool
    """If True, the schema is only used if referenced as a trigger_schema_id or link schema_id."""


def get_default(
    schema: dict[str, Any], field: Optional[str] = None
) -> Union[str, bool]:
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
        if isinstance(def_value, (str, bool)):
            return def_value
        raise TypeError(
            f"Default value for field '{field}' is not a string or boolean."
        )
    raise KeyError(f"Default value for field '{field}' not found in schema.")
