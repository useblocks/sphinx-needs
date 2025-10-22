from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from sphinx.errors import SphinxError

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.need_item import NeedItem
from sphinx_needs.schema.config import (
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
    need: NeedItem
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

    if os.name == "nt":  # Windows
        # Sanitize filename for Windows compatibility
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # Also remove control characters (0-31)
        filename = re.sub(r"[\x00-\x1f]", "_", filename)
        # Limit filename length to 250 characters for Windows compatibility
        if len(filename) > 250:
            # Keep the extension if present, truncate the base name
            if "." in filename:
                name, ext = filename.rsplit(".", 1)
                filename = name[: 247 - len(ext) - 1] + "..." + "." + ext
            else:
                filename = filename[:247] + "..."

    with (debug_dir / f"{filename}.json").open("w") as fp:
        json.dump(dict(warning["need"]), fp, indent=2)
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


class WarningDetails(TypedDict):
    severity: NotRequired[str]
    field: NotRequired[str]
    need_path: NotRequired[str]
    schema_path: NotRequired[str]
    validation_msg: NotRequired[str]
    user_msg: NotRequired[str]


class JSONFormattedWarningChild(TypedDict):
    """JSON Formatted child warning (nested within parent warnings)."""

    subtype: str
    details: WarningDetails
    children: list[ChildWarning]


class ChildWarning(TypedDict):
    need_id: str
    warning: JSONFormattedWarningChild


class JSONFormattedWarning(TypedDict):
    """JSON Formatted warning info for the ontology validation."""

    log_lvl: Literal["warning", "error"]
    type: str
    subtype: str
    details: WarningDetails
    children: list[ChildWarning]


class OntologyReportJSON(TypedDict):
    validation_summary: str
    validated_needs_per_second: int | float
    validated_needs_count: int
    validation_warnings: dict[str, list[JSONFormattedWarning]]


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
    log_lvl: Literal["warning", "error"]

    # Map severity to logger level and type
    if warning["severity"] == SeverityEnum.config_error:
        title = (
            f"Need '{warning['need']['id']}' has configuration errors:"
            if has_title
            else ""
        )
        log_lvl = "error"
        type_str = "sn_schema"
    elif warning["severity"] == SeverityEnum.violation:
        title = (
            f"Need '{warning['need']['id']}' has schema violations:"
            if has_title
            else ""
        )
        log_lvl = "error"
        type_str = "sn_schema_violation"
    elif warning["severity"] == SeverityEnum.warning:
        title = (
            f"Need '{warning['need']['id']}' has schema warnings:" if has_title else ""
        )
        log_lvl = "warning"
        type_str = "sn_schema_warning"
    elif warning["severity"] == SeverityEnum.info:
        title = f"Need '{warning['need']['id']}' has schema infos:" if has_title else ""
        log_lvl = "warning"
        type_str = "sn_schema_info"
    else:
        # SeverityEnum.none is filtered out earlier
        raise SphinxError("Unexpected severity 'none' in console formatting.")

    formatted_warning = FormattedWarning(
        log_lvl=log_lvl,
        type=type_str,
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

    Warnings with severity 'none' are filtered out as they are only for debugging.

    :returns: tuple [log level, type, sub-type, message]
    """
    formatted_warnings: list[FormattedWarning] = []
    for warnings in need_2_warnings.values():
        for warning in warnings:
            # Skip warnings with severity none (debug only)
            if warning["severity"] == SeverityEnum.none:
                continue
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


def _get_json_formatted_child_recurse(
    warning: OntologyWarning, level: int
) -> JSONFormattedWarningChild:
    """Helper function to format nested child warnings without log_lvl and type."""
    warning_details = get_json_warning_details(level, warning)

    formatted_child = JSONFormattedWarningChild(
        subtype=warning["rule"].value,
        details=warning_details,
        children=[],
    )
    if "children" in warning:
        for child_warning in warning["children"]:
            formatted_child["children"].append(
                {
                    "need_id": child_warning["need"]["id"],
                    "warning": _get_json_formatted_child_recurse(
                        child_warning, level=level + 1
                    ),
                }
            )
    return formatted_child


def get_json_formatted_warnings_recurse(
    warning: OntologyWarning, level: int
) -> list[JSONFormattedWarning]:
    """
    Recursively format warning details.

    :param warning: The OntologyWarning to format.
    :param level: The OntologyWarning level (0 for root).
    :return: A list of JSONFormattedWarning objects.
    """
    warning_details = get_json_warning_details(level, warning)

    log_lvl: Literal["warning", "error"]

    # Root level warning includes log_lvl and type
    # Map severity to logger level and type
    if warning["severity"] == SeverityEnum.config_error:
        log_lvl = "error"
        type_str = "sn_schema"
    elif warning["severity"] == SeverityEnum.violation:
        log_lvl = "error"
        type_str = "sn_schema_violation"
    elif warning["severity"] == SeverityEnum.warning:
        log_lvl = "warning"
        type_str = "sn_schema_warning"
    elif warning["severity"] == SeverityEnum.info:
        log_lvl = "warning"
        type_str = "sn_schema_info"
    else:
        # SeverityEnum.none is filtered out earlier
        raise SphinxError("Unexpected severity 'none' in JSON formatting.")

    formatted_warning = JSONFormattedWarning(
        log_lvl=log_lvl,
        type=type_str,
        subtype=warning["rule"].value,
        details=warning_details,
        children=[],
    )
    if "children" in warning:
        for child_warning in warning["children"]:
            formatted_warning["children"].append(
                {
                    "need_id": child_warning["need"]["id"],
                    "warning": _get_json_formatted_child_recurse(
                        child_warning, level=level + 1
                    ),
                }
            )
    return [formatted_warning]


def get_json_formatted_warnings(
    need_2_warnings: dict[str, list[OntologyWarning]],
) -> dict[str, list[JSONFormattedWarning]]:
    """
    JSON formatted warnings from the ontology validation for each need.

    Warnings with severity 'none' are filtered out as they are only for debugging.

    :param need_2_warnings: A dictionary mapping need IDs to their warnings.
    :return: A dictionary with list of JSONFormattedWarning objects.
    """
    need_formatted_warnings: dict[str, list[JSONFormattedWarning]] = {}
    for need_id, warnings in need_2_warnings.items():
        formatted_warnings: list[JSONFormattedWarning] = []
        for warning in warnings:
            # Skip warnings with severity none (debug only)
            if warning["severity"] == SeverityEnum.none:
                continue
            new_warnings = get_json_formatted_warnings_recurse(warning=warning, level=0)
            formatted_warnings.extend(new_warnings)

        need_formatted_warnings[need_id] = formatted_warnings
    return need_formatted_warnings


def get_json_warning_details(base_lvl: int, warning: OntologyWarning) -> WarningDetails:
    """Get JSON formatted warning details."""
    warning_details: WarningDetails = {}

    if base_lvl == 0:
        # top level warning already reports the severity
        warning_details["severity"] = warning["severity"].name

    if "field" in warning:
        warning_details["field"] = warning["field"]
    if warning["need_path"]:
        need_path_str = " > ".join(warning["need_path"])
        warning_details["need_path"] = need_path_str
    if "schema_path" in warning:
        schema_path_str = " > ".join(warning["schema_path"])
        warning_details["schema_path"] = schema_path_str
    if "user_message" in warning:
        warning_details["user_msg"] = warning["user_message"]
    if "validation_message" in warning:
        warning_details["validation_msg"] = warning["validation_message"]

    return warning_details


def clear_debug_dir(config: NeedsSphinxConfig) -> None:
    debug_path = Path(config.schema_debug_path)
    if debug_path.exists():
        for file in debug_path.glob("*"):
            file.unlink()
    else:
        debug_path.mkdir()


def generate_json_schema_validation_report(
    duration: float,
    need_2_warnings: dict[str, list[OntologyWarning]],
    report_file_path: Path,
    validated_needs_count: int,
    validated_rate: int | float,
) -> None:
    """
    Generate a JSON schema validation report.

    :param duration: The duration of the validation process.
    :param need_2_warnings: A mapping of needs to their validation warnings.
    :param report_file_path: The path to the report file.
    :param validated_needs_count: The number of validated needs.
    :param validated_rate: The rate of validated needs per second.
    """
    json_formatted_warnings: dict[str, list[JSONFormattedWarning]] = {}
    if need_2_warnings:
        json_formatted_warnings = get_json_formatted_warnings(need_2_warnings)
    ontology_report: OntologyReportJSON = {
        "validation_summary": (
            f"Schema validation completed with {len(json_formatted_warnings)} warning(s) in {duration:.3f} seconds. "
            f"Validated {validated_rate} needs/s."
        ),
        "validated_needs_per_second": validated_rate,
        "validated_needs_count": validated_needs_count,
        "validation_warnings": json_formatted_warnings,
    }
    # Store ontology report in JSON file
    with report_file_path.open("w") as fp:
        json.dump(ontology_report, fp, indent=2)
