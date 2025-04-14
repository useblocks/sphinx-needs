import json
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.schema.config import MAP_RULE_SEVERITY, MessageRuleEnum, SeverityEnum


class OntologyWarning(TypedDict, total=True):
    """Warning message for the ontology validation."""

    rule: MessageRuleEnum
    severity: SeverityEnum
    user_message: Optional[str]
    validation_message: Optional[str]
    need: dict[str, Any]
    schema: dict[str, Any]
    schema_path: Optional[list[str]]
    need_path: Optional[list[str]]
    field: Optional[str]


_sep = "__"
"""Separator between nested parts of debug output file names."""


def save_debug_files(
    need: dict[str, Any],
    schema: dict[str, Any],
    need_path: list[str],
    schema_path: list[str],
    config: NeedsSphinxConfig,
    message: OntologyWarning,
) -> None:
    """Write debug json and schema files."""
    if not config.schemas_debug_active:
        return
    if message["rule"] in config.schemas_debug_ignore:
        return
    debug_dir = Path(config.schemas_debug_path)

    filename = _sep.join(need_path) + _sep + _sep.join(schema_path)
    with (debug_dir / f"{filename}.json").open("w") as fp:
        json.dump(need, fp, indent=2)
    with (debug_dir / f"{filename}.schema.json").open("w") as fp:
        json.dump(schema, fp, indent=2)

    messages = ""
    if message["user_message"] is not None:
        messages += f"User message:\n{message['user_message']}\n"
    if message["validation_message"] is not None:
        messages += f"Validation message:\n{message['validation_message']}\n"
    if messages:
        with (debug_dir / f"{filename}.txt").open("w") as fp:
            fp.write(messages)


def report_message(
    config: NeedsSphinxConfig,
    warnings: list[OntologyWarning],
    need: dict[str, Any],
    schema: dict[str, Any],
    rule: MessageRuleEnum,
    need_path: list[str],
    schema_path: list[str],
    severity: Optional[SeverityEnum] = None,
    user_msg: Optional[str] = None,
    validation_msg: Optional[str] = None,
    field: Optional[str] = None,
) -> None:
    if severity is None:
        severity = MAP_RULE_SEVERITY[rule]
    warning = OntologyWarning(
        rule=rule,
        severity=severity,
        user_message=user_msg,
        validation_message=validation_msg,
        need=need,
        schema=schema,
        schema_path=schema_path,
        need_path=need_path,
        field=field,
    )
    if severity != SeverityEnum.none:
        warnings.append(warning)
    save_debug_files(
        need=need,
        schema=schema,
        need_path=need_path,
        schema_path=schema_path,
        config=config,
        message=warning,
    )


class FormattedWarning(TypedDict):
    """Formatted warning message for the ontology validation."""

    log_lvl: Literal["warning", "error"]
    type: str
    subtype: str
    message: str


def get_formatted_warnings(
    config: NeedsSphinxConfig, need_2_warnings: dict[str, list[OntologyWarning]]
) -> list[FormattedWarning]:
    """
    Pretty format warnings from the ontology validation.

    :returns: tuple [log level, type, sub-type, message]
    """
    warnings = []
    for need_id, need_warnings in need_2_warnings.items():
        for warning in need_warnings:
            report = False
            severity = warning["severity"]
            config_severity = SeverityEnum[config.schemas_severity]
            report = severity.value >= config_severity.value
            if report:
                warning_msg = ""

                lvl_severity = 1
                lvl_field = 1
                lvl_need_path = 2
                lvl_schema_path = 2
                lvl_validation_msg = 2
                lvl_user_msg = 2

                warning_msg += (
                    "\n" + lvl_severity * 2 * " " + f"Severity: {severity.name}"
                )
                if warning["field"]:
                    warning_msg += (
                        "\n" + lvl_field * 2 * " " + f"Field: {warning['field']}"
                    )
                if warning["need_path"]:
                    need_path_str = " > ".join(warning["need_path"])
                    warning_msg += (
                        "\n"
                        + lvl_need_path * 2 * " "
                        + f"Need path:      {need_path_str}"
                    )
                if warning["schema_path"]:
                    schema_path_str = " > ".join(warning["schema_path"])
                    warning_msg += (
                        "\n"
                        + lvl_schema_path * 2 * " "
                        + f"Schema path:    {schema_path_str}"
                    )
                if warning["user_message"] is not None:
                    warning_msg += (
                        "\n"
                        + lvl_user_msg * 2 * " "
                        + f"User message:   {warning['user_message']}"
                    )
                if warning["validation_message"] is not None:
                    warning_msg += (
                        "\n"
                        + lvl_validation_msg * 2 * " "
                        + f"Schema message: {warning['validation_message']}"
                    )

                if severity == SeverityEnum.config_error:
                    warnings.append(
                        FormattedWarning(
                            log_lvl="error",
                            type="sn_schema",
                            subtype=warning["rule"].value,
                            message=f"Need '{need_id}' has configuration errors:{warning_msg}",
                        )
                    )
                else:
                    warnings.append(
                        FormattedWarning(
                            log_lvl="warning",
                            type="sn_schema",
                            subtype=warning["rule"].value,
                            message=f"Need '{need_id}' has validation errors:{warning_msg}",
                        )
                    )
    return warnings


def clear_debug_dir(config: NeedsSphinxConfig) -> None:
    debug_path = Path(config.schemas_debug_path)
    if debug_path.exists():
        for file in debug_path.glob("*"):
            file.unlink()
    else:
        debug_path.mkdir()
