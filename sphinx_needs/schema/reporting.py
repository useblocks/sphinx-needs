from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType
from sphinx_needs.schema.config import (
    MAP_RULE_DEFAULT_SEVERITY,
    MessageRuleEnum,
    NeedFieldsSchemaWithVersionType,
    SeverityEnum,
)

if TYPE_CHECKING:
    from typing_extensions import NotRequired


class OntologyWarning(TypedDict):
    """
    Warning message for the ontology validation.

    These are final messages that are reported to the user.
    The structure is a flattened version of the validation report ReportSchemaType.
    """

    rule: MessageRuleEnum
    severity: SeverityEnum
    user_message: NotRequired[str]
    validation_message: NotRequired[str]
    need: NeedsInfoType
    reduced_need: NotRequired[dict[str, Any]]
    final_schema: NotRequired[NeedFieldsSchemaWithVersionType]
    schema_path: NotRequired[list[str]]
    need_path: list[str]
    field: NotRequired[str]
    children: NotRequired[list[OntologyWarning]]


class ValidateNeedMessageType(TypedDict):
    """Single validation message."""

    field: str
    """Affected need field."""
    message: str
    """Validation message."""
    schema_path: list[str]
    """Nested path in the single schema where the error occurred."""


class ValidateNeedType(TypedDict):
    """
    Return structure for validate_local_need.

    Specifically made for this as it misses the outer validation context.
    """

    messages: list[ValidateNeedMessageType]
    """List of validation messages or empty if successful."""
    final_schema: NeedFieldsSchemaWithVersionType
    """The assembled final schema that was used for validation."""
    reduced_need: dict[str, Any]
    """The need as it was validated (reduced form)."""


_field_sep = "."
"""Separator between nested parts of field names in debug output file names."""
_sep = "__"
"""Separator between nested parts of debug output file names."""


def filter_warnings_severity(
    config: NeedsSphinxConfig,
    warnings: list[OntologyWarning],
    schema_root_severity: SeverityEnum | None = None,
) -> list[OntologyWarning]:
    """
    Filter warnings by severity.

    There are multiple severity sources:
    - needs_config.schema_severity: the minimum severity for warnings to be reported
    - needs_config.schema_definitions: contains a severity field that determines the reported rule severity
    - schemas.config.MAP_RULE_DEFAULT_SEVERITY: default if the schemas severities field is not set

    Precedence for reporting:
    - if the rule has a default severity of none, it is ignored; those are never of interest
      as reporting target, only for debugging purposes
    - if the schema root severity is set, it overrides the rule severity
    - if the schema root severity is not set, the rule default severity is used
    """
    min_severity_for_report = SeverityEnum[config.schema_severity]
    filtered_warnings = []
    for warning in warnings:
        rule_default_severity = MAP_RULE_DEFAULT_SEVERITY[warning["rule"]]
        if rule_default_severity is SeverityEnum.none:
            # rule is not of interest for final reporting (e.g. unselected needs)
            # it might be logged for schema debugging however
            continue
        # the warning severity is overriden by the schema root severity
        # if it is unset, the rule mapping MAP_RULE_DEFAULT_SEVERITY is used
        warning_severity = (
            schema_root_severity
            if schema_root_severity is not None
            else warning["severity"]
        )
        if warning_severity >= min_severity_for_report:
            filtered_warnings.append(warning)
    return filtered_warnings


def save_debug_files(
    config: NeedsSphinxConfig, warnings: list[OntologyWarning]
) -> None:
    """
    Write list of warnings as debug files.

    :param config: NeedsSphinxConfig object with debug settings.
    :param warnings: List of OntologyWarning objects to save.
    """
    if not config.schema_debug_active:
        return
    for warning in warnings:
        save_debug_file(config, warning)


def save_debug_file(
    config: NeedsSphinxConfig,
    warning: OntologyWarning,
) -> None:
    """Write debug json and schema files."""
    if not config.schema_debug_active:
        return
    if warning["rule"].name in config.schema_debug_ignore:
        return
    debug_dir = Path(config.schema_debug_path)

    filename = _field_sep.join(warning["need_path"])
    if schema_path := warning.get("schema_path"):
        filename += _sep + _field_sep.join(schema_path)
    filename += _sep + warning["rule"].name

    with (debug_dir / f"{filename}.json").open("w") as fp:
        json.dump(warning["need"], fp, indent=2)
    if reduced_need := warning.get("reduced_need"):
        with (debug_dir / f"{filename}.reduced.json").open("w") as fp:
            json.dump(reduced_need, fp, indent=2)
    if final_schema := warning.get("final_schema"):
        with (debug_dir / f"{filename}.schema.json").open("w") as fp:
            json.dump(final_schema, fp, indent=2)

    messages = ""
    if user_message := warning.get("user_message"):
        messages += f"User message:\n{user_message}\n"
    if validation_message := warning.get("validation_message"):
        messages += f"Validation message:\n{validation_message}\n"
    with (debug_dir / f"{filename}.txt").open("w") as fp:
        fp.write(messages)


class FormattedWarning(TypedDict):
    """Formatted warning message for the ontology validation."""

    log_lvl: Literal["warning", "error"]
    type: str
    subtype: str
    message: str


def get_formatted_warnings_recurse(
    warning: OntologyWarning, level: int
) -> list[FormattedWarning]:
    """
    Recursively format a warning message with indentation.

    :param warning: The OntologyWarning to format.
    :return: A list of FormattedWarning objects.
    """
    formatted_warnings: list[FormattedWarning] = []
    warning_msg = get_warning_msg(level, warning)
    has_title = level == 0
    if warning["severity"] == SeverityEnum.config_error:
        title = (
            f"Need '{warning['need']['id']}' has configuration errors:"
            if has_title
            else ""
        )
        formatted_warning = FormattedWarning(
            log_lvl="error",
            type="sn_schema",
            subtype=warning["rule"].value,
            message=f"{title}{warning_msg}",
        )
    else:
        title = (
            f"Need '{warning['need']['id']}' has validation errors:"
            if has_title
            else ""
        )
        formatted_warning = FormattedWarning(
            log_lvl="warning",
            type="sn_schema",
            subtype=warning["rule"].value,
            message=f"{title}{warning_msg}",
        )
    formatted_warnings.append(formatted_warning)
    if "children" in warning:
        for child_warning in warning["children"]:
            formatted_child_warnings = get_formatted_warnings_recurse(
                warning=child_warning, level=level + 1
            )
            indent = "  " * (1 + level + 1)
            for formatted_child_warning in formatted_child_warnings:
                formatted_warning["message"] += (
                    f"\n\n{indent}Details for {child_warning['need']['id']}"
                    + formatted_child_warning["message"]
                )
            # formatted_warnings.extend(formatted_child_warnings)
    return formatted_warnings


def get_formatted_warnings(
    need_2_warnings: dict[str, list[OntologyWarning]],
) -> list[FormattedWarning]:
    """
    Pretty format warnings from the ontology validation.

    :returns: tuple [log level, type, sub-type, message]
    """
    formatted_warnings: list[FormattedWarning] = []
    for warnings in need_2_warnings.values():
        for warning in warnings:
            new_warnings = get_formatted_warnings_recurse(warning=warning, level=0)
            formatted_warnings.extend(new_warnings)
    return formatted_warnings


def get_warning_msg(base_lvl: int, warning: OntologyWarning) -> str:
    """Craft a properly indented warning message."""
    warning_msg = ""

    lvl_severity = 1
    lvl_field = 1
    lvl_need_path = 1
    lvl_schema_path = 1
    lvl_validation_msg = 1
    lvl_user_msg = 1

    def nl_indent(level: int) -> str:
        return "\n" + (base_lvl + level) * 2 * " "

    if base_lvl == 0:
        # top level warning already reports the severity
        warning_msg += (
            nl_indent(lvl_severity) + f"Severity:       {warning['severity'].name}"
        )
    if "field" in warning:
        warning_msg += nl_indent(lvl_field) + f"Field:          {warning['field']}"
    if warning["need_path"]:
        need_path_str = " > ".join(warning["need_path"])
        warning_msg += nl_indent(lvl_need_path) + f"Need path:      {need_path_str}"
    if "schema_path" in warning:
        schema_path_str = " > ".join(warning["schema_path"])
        warning_msg += nl_indent(lvl_schema_path) + f"Schema path:    {schema_path_str}"
    if "user_message" in warning:
        warning_msg += (
            nl_indent(lvl_user_msg) + f"User message:   {warning['user_message']}"
        )
    if "validation_message" in warning:
        warning_msg += (
            nl_indent(lvl_validation_msg)
            + f"Schema message: {warning['validation_message']}"
        )

    return warning_msg


def clear_debug_dir(config: NeedsSphinxConfig) -> None:
    debug_path = Path(config.schema_debug_path)
    if debug_path.exists():
        for file in debug_path.glob("*"):
            file.unlink()
    else:
        debug_path.mkdir()
