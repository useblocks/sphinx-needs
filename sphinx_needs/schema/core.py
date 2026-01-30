"""SN extension for schema validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, TypedDict, cast

import jsonschema_rs
from jsonschema_rs import RegexOptions, ValidationError, Validator

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.need_item import NeedItem
from sphinx_needs.schema.config import (
    MAP_RULE_DEFAULT_SEVERITY,
    MAX_NESTED_NETWORK_VALIDATION_LEVELS,
    MessageRuleEnum,
    NeedFieldsSchemaType,
    NeedFieldsSchemaWithVersionType,
    SchemasRootType,
    SeverityEnum,
    ValidateSchemaType,
    get_schema_name,
)
from sphinx_needs.schema.reporting import (
    OntologyWarning,
    save_debug_files,
)
from sphinx_needs.schema.utils import get_properties_from_schema
from sphinx_needs.views import NeedsView

if TYPE_CHECKING:
    from typing_extensions import NotRequired

# TODO(Marco): error for conflicting unevaluatedProperties

_SCHEMA_VERSION: Final[str] = "https://json-schema.org/draft/2020-12/schema"
"""
JSON schema metaversion to use.

The implementation requires at least draft 2019-09 as unevaluatedProperties was added there.
"""


def validate_option_fields(
    config: NeedsSphinxConfig,
    schema: NeedFieldsSchemaType,
    field_properties: Mapping[str, NeedFieldProperties],
    needs: NeedsView,
) -> dict[str, list[OntologyWarning]]:
    """Validate schema originating from extra option definitions."""
    need_2_warnings: dict[str, list[OntologyWarning]] = {}
    validator = compile_validator(schema)
    for need in needs.values():
        schema_warnings = get_ontology_warnings(
            need,
            field_properties,
            validator,
            fail_rule=MessageRuleEnum.field_fail,
            success_rule=MessageRuleEnum.field_success,
            schema_path=["fields", "schema"],
            need_path=[need["id"]],
        )
        save_debug_files(config, schema_warnings)
        if schema_warnings:
            need_2_warnings[need["id"]] = schema_warnings
    return need_2_warnings


def validate_link_options(
    config: NeedsSphinxConfig,
    schema: NeedFieldsSchemaType,
    field_properties: Mapping[str, NeedFieldProperties],
    needs: NeedsView,
) -> dict[str, list[OntologyWarning]]:
    """Validate schema originating from extra link definitions."""
    need_2_warnings: dict[str, list[OntologyWarning]] = {}
    validator = compile_validator(schema)
    for need in needs.values():
        schema_warnings = get_ontology_warnings(
            need,
            field_properties,
            validator,
            fail_rule=MessageRuleEnum.extra_link_fail,
            success_rule=MessageRuleEnum.extra_link_success,
            schema_path=["extra_links", "schema"],
            need_path=[need["id"]],
        )
        save_debug_files(config, schema_warnings)
        if schema_warnings:
            need_2_warnings[need["id"]] = schema_warnings
    return need_2_warnings


def validate_type_schema(
    config: NeedsSphinxConfig,
    schema: SchemasRootType,
    needs: NeedsView,
    field_properties: Mapping[str, NeedFieldProperties],
) -> dict[str, list[OntologyWarning]]:
    """Validate needs against a type schema."""
    need_2_warnings: dict[str, list[OntologyWarning]] = {}

    schema_name = get_schema_name(schema)
    validator = (
        compile_validator(cast(NeedFieldsSchemaType, schema["select"]))
        if schema.get("select")
        else None
    )
    user_severity = SeverityEnum[schema["severity"]] if "severity" in schema else None
    local_network_schema: ValidateSchemaType = {}
    if "local" in schema["validate"]:
        local_network_schema["local"] = schema["validate"]["local"]
    if "network" in schema["validate"]:
        local_network_schema["network"] = schema["validate"]["network"]

    validator_cache: dict[tuple[str, ...], SchemaValidator] = {}

    for need in needs.values():
        # maintain state for nested network validation
        if validator is not None:
            new_warnings_select = get_ontology_warnings(
                need,
                field_properties,
                validator,
                fail_rule=MessageRuleEnum.select_fail,
                success_rule=MessageRuleEnum.select_success,
                schema_path=[schema_name, "select"],
                need_path=[need["id"]],
            )
            save_debug_files(config, new_warnings_select)
            # filter warnings not required as select has severity none
            if any_not_of_rule(new_warnings_select, MessageRuleEnum.select_success):
                # need is not selected
                continue

        _, new_warnings_recurse = recurse_validate_schemas(
            config,
            need,
            needs,
            user_message=schema.get("message"),
            field_properties=field_properties,
            schema=local_network_schema,
            severity=user_severity,
            schema_path=[schema_name],
            need_path=[need["id"]],
            validator_cache=validator_cache,
            recurse_level=0,
        )
        if new_warnings_recurse:
            need_2_warnings[need["id"]] = new_warnings_recurse

    return need_2_warnings


def recurse_validate_schemas(
    config: NeedsSphinxConfig,
    need: NeedItem,
    needs: NeedsView,
    user_message: str | None,
    field_properties: Mapping[str, NeedFieldProperties],
    schema: ValidateSchemaType,
    schema_path: list[str],
    need_path: list[str],
    recurse_level: int,
    validator_cache: dict[tuple[str, ...], SchemaValidator],
    severity: SeverityEnum | None = None,
) -> tuple[bool, list[OntologyWarning]]:
    """
    Recursively validate a need against type schemas.

    The bool success bit indicates whether local and downstream validation were successful.
    The returned list of OntologyWarning objects contains warnings
    that are already filtered by user severity and can directly be used for user reporting.
    """
    if recurse_level > MAX_NESTED_NETWORK_VALIDATION_LEVELS:
        rule = MessageRuleEnum.network_max_nest_level
        warning: OntologyWarning = {
            "rule": rule,
            "severity": MAP_RULE_DEFAULT_SEVERITY[rule],
            "validation_message": (
                f"Maximum network validation recursion level {MAX_NESTED_NETWORK_VALIDATION_LEVELS} reached."
            ),
            "need": need,
            "schema_path": schema_path,
            "need_path": need_path,
        }
        if user_message is not None:
            warning["user_message"] = user_message
        return False, [warning]

    warnings: list[OntologyWarning] = []
    success = True
    if "local" in schema:
        rule_success = (
            MessageRuleEnum.local_success
            if recurse_level == 0
            else MessageRuleEnum.network_local_success
        )
        rule_fail = (
            MessageRuleEnum.local_fail
            if recurse_level == 0
            else MessageRuleEnum.network_local_fail
        )
        if (validator := validator_cache.get((*schema_path, "local"))) is None:
            validator = compile_validator(cast(NeedFieldsSchemaType, schema["local"]))
            validator_cache[(*schema_path, "local")] = validator
        warnings_local = get_ontology_warnings(
            need,
            field_properties,
            validator,
            rule_fail,
            rule_success,
            schema_path=[*schema_path, "local"],
            need_path=need_path,
            user_message=user_message if recurse_level == 0 else None,
            user_severity=severity if recurse_level == 0 else None,
        )
        save_debug_files(config, warnings_local)
        warnings.extend(warnings_local)
        if any_not_of_rule(warnings_local, rule_success):
            success = False
    if "network" in schema:
        for link_type, link_schema in schema["network"].items():
            items_targets_ok: list[str] = []
            """List of target need ids for items validation that passed."""
            items_targets_nok: list[str] = []
            """List of target need ids for items validation that failed."""
            items_warnings_per_target: dict[str, list[OntologyWarning]] = {}
            """Map of target need id to warnings for failed items validation."""
            contains_targets_ok: list[str] = []
            """List of target need ids for contains validation that passed."""
            contains_targets_nok: list[str] = []
            """List of target need ids for contains validation that failed."""
            contains_warnings_per_target: dict[str, list[OntologyWarning]] = {}
            """Map of target need id to warnings for failed contains validation."""
            schema_path_items = [
                *schema_path,
                "validate",
                "network",
                link_type,
                "items",
            ]
            schema_path_contains = [
                *schema_path,
                "validate",
                "network",
                link_type,
                "contains",
            ]
            for target_need_id in need[link_type]:
                # collect all downstream warnings for broken links, items and contains
                # evaluation happens later
                try:
                    target_need = needs[target_need_id]
                except KeyError:
                    # target need does not exist (broken link)
                    rule = MessageRuleEnum.network_missing_target
                    msg = f"Broken link of type '{link_type}' to '{target_need_id}'"
                    # report it directly, it's not a minmax warning and the target need is ignored
                    # in the minmax checks
                    warnings.append(
                        {
                            "rule": rule,
                            "severity": get_severity(rule, severity),
                            "validation_message": msg,
                            "need": need,
                            "schema_path": [
                                *schema_path,
                                "validate",
                                "network",
                                link_type,
                            ],
                            "need_path": [*need_path, link_type],
                        }
                    )
                    if recurse_level == 0 and user_message is not None:
                        warnings[-1]["user_message"] = user_message
                    continue

                need_path_link = [*need_path, link_type, target_need_id]
                # Handle items validation - all items must pass
                if link_schema.get("items"):
                    new_success, new_warnings = recurse_validate_schemas(
                        config=config,
                        need=target_need,
                        needs=needs,
                        user_message=user_message,
                        field_properties=field_properties,
                        schema=link_schema["items"],
                        schema_path=schema_path_items,
                        need_path=need_path_link,
                        recurse_level=recurse_level + 1,
                        validator_cache=validator_cache,
                        severity=severity,
                    )
                    if new_success:
                        items_targets_ok.append(target_need_id)
                    else:
                        items_targets_nok.append(target_need_id)
                    items_warnings_per_target[target_need_id] = new_warnings
                else:
                    items_targets_ok.append(target_need_id)

                # Handle contains validation - at least some items must pass
                if link_schema.get("contains"):
                    new_success, new_warnings = recurse_validate_schemas(
                        config=config,
                        need=target_need,
                        needs=needs,
                        user_message=user_message,
                        field_properties=field_properties,
                        schema=link_schema["contains"],
                        schema_path=schema_path_contains,
                        need_path=need_path_link,
                        recurse_level=recurse_level + 1,
                        validator_cache=validator_cache,
                        severity=severity,
                    )
                    if new_success:
                        contains_targets_ok.append(target_need_id)
                    else:
                        contains_targets_nok.append(target_need_id)
                    contains_warnings_per_target[target_need_id] = new_warnings
                else:
                    contains_targets_ok.append(target_need_id)

            # Check items validation results
            items_success = True
            if link_schema.get("items") and items_targets_nok:
                items_success = False
                # Add warnings for failed items validation
                items_nok_warnings = [
                    warning
                    for target_id in items_targets_nok
                    for warning in items_warnings_per_target[target_id]
                ]
                rule = MessageRuleEnum.network_items_fail
                msg = (
                    f"Items validation failed for links of type '{link_type}' "
                    f"to {', '.join(items_targets_nok)}"
                )
                if items_targets_ok:
                    msg += f" / ok: {', '.join(items_targets_ok)}"
                if items_targets_nok:
                    msg += f" / nok: {', '.join(items_targets_nok)}"
                warning = {
                    "rule": rule,
                    "severity": get_severity(rule, severity),
                    "validation_message": msg,
                    "need": need,
                    "schema_path": schema_path_items,
                    "need_path": [*need_path, link_type],
                    "children": items_nok_warnings,  # user is interested in these
                }
                if recurse_level == 0 and user_message is not None:
                    # user message only added to the root validation
                    warning["user_message"] = user_message
                warnings.extend(items_nok_warnings)

            # Check contains validation results
            contains_success = True
            if link_schema.get("contains"):
                contains_warnings: list[OntologyWarning] = []
                contains_cnt_ok = len(contains_targets_ok)
                contains_cnt_nok = len(contains_targets_nok)
                min_contains = 1  # default if minContains is not set
                if "minContains" in link_schema:
                    min_contains = link_schema["minContains"]
                if contains_cnt_ok < min_contains:
                    rule = MessageRuleEnum.network_contains_too_few
                    msg = f"Too few valid links of type '{link_type}' ({contains_cnt_ok} < {min_contains})"
                    if contains_cnt_ok > 0:
                        msg += f" / ok: {', '.join(contains_targets_ok)}"
                    if contains_cnt_nok > 0:
                        msg += f" / nok: {', '.join(contains_targets_nok)}"
                    contains_nok_warnings = [
                        warning
                        for target_id in contains_targets_nok
                        for warning in contains_warnings_per_target[target_id]
                    ]
                    contains_warnings.append(
                        {
                            "rule": rule,
                            "severity": get_severity(rule, severity),
                            "validation_message": msg,
                            "need": need,
                            "schema_path": schema_path_contains,
                            "need_path": [*need_path, link_type],
                            "children": contains_nok_warnings,  # user is interested in these
                        }
                    )
                    if recurse_level and user_message is not None:
                        contains_warnings[-1]["user_message"] = user_message
                    contains_success = False
                if "maxContains" in link_schema:
                    max_contains = link_schema["maxContains"]
                    if contains_cnt_ok > max_contains:
                        rule = MessageRuleEnum.network_contains_too_many
                        msg = f"Too many valid links of type '{link_type}' ({contains_cnt_ok} > {max_contains})"
                        if contains_cnt_ok > 0:
                            msg += f" / ok: {', '.join(contains_targets_ok)}"
                        if contains_cnt_nok > 0:
                            msg += f" / nok: {', '.join(contains_targets_nok)}"
                        contains_warnings.append(
                            {
                                "rule": rule,
                                "severity": get_severity(rule, severity),
                                "validation_message": msg,
                                "need": need,
                                "schema_path": schema_path_contains,
                                "need_path": [*need_path, link_type],
                                # children not passed, no interest in too much success
                            }
                        )
                        if recurse_level == 0 and user_message is not None:
                            # user message only added to the root validation
                            contains_warnings[-1]["user_message"] = user_message
                        contains_success = False

                warnings.extend(contains_warnings)

            # Overall success requires both items and minmax validation to pass
            if not (items_success and contains_success):
                success = False

    return success, warnings


class NeedFieldProperties(TypedDict):
    """Properties of a need field used for schema validation."""

    field_type: str
    default: NotRequired[Any]


def reduce_need(
    need: NeedItem,
    field_properties: Mapping[str, NeedFieldProperties],
    schema_properties: set[str],
) -> dict[str, Any]:
    """Reduce a need to the subset relevant for schema validation.

    The returned mapping is used as the validation instance (especially for
    ``unevaluatedProperties``) to focus on user-controlled fields.

    Rules:

    - ``None`` values are always dropped (schema validation cannot handle null types).
    - Extra fields are included based on their configured default (independent of
      ``schema_properties``):

      - If the default is ``None``, any non-``None`` value is kept.
      - If the default is ``""`` (SN5-style empty), the value is kept only if it is not ``""``.
      - For any other default value, the field is kept as-is.

    - Link fields are included only if they are non-empty (independent of ``schema_properties``).
    - Core fields are included if they are covered by ``schema_properties``.
      Additionally, ``status`` is kept if it is non-``None`` and ``tags`` is kept if it is non-empty.

    SN5 vs SN6 empty-vs-missing semantics for extra options:

    - Without a field schema (SN5-style), unset and present-but-empty (``:opt:``) both become
      ``""``, so "unset" and "set-but-empty" cannot be distinguished.
    - With a field schema (SN6), unset nullable options default to ``None``, while ``:opt:``
      results in ``""``. This allows distinguishing "unset" from "set-but-empty".

    In this reduction, that distinction matters for extra fields: ``""`` is dropped if the
    default is also ``""`` (SN5-style), while ``""`` is kept if the default is ``None``
    (SN6-style), so set-but-empty can be treated as actively set.

    For link fields, missing vs empty cannot be distinguished (both result in ``[]``).

    :param need: Need to reduce.
    :param field_properties: Field defaults/types used to detect default values.
    :param schema_properties: Set of field names covered by the current schema.
    :return: Reduced mapping used as schema validation instance.
    """
    reduced_need: dict[str, Any] = {}

    for field, value in need.iter_extra_items():
        if value is None:
            # field is unset, and schema validation cannot handle null types
            continue

        schema_field = field_properties[field]
        if "default" in schema_field:
            if schema_field["default"] is None:
                # keep all non-None values - they are actively set
                reduced_need[field] = value
            elif schema_field["default"] == "":
                # SN5 case: only keep non-empty values
                if value != "":
                    reduced_need[field] = value
            else:
                # keep the value - there is a default that is not None/"" or a real RST value
                reduced_need[field] = value

    for field, value in need.iter_links_items():
        if value:
            # keep non-empty link fields
            reduced_need[field] = value

    for field, value in need.iter_core_items():
        if value is None:
            continue

        if field in schema_properties:
            # actively included by schema - include to validate constraints
            reduced_need[field] = value
            continue

        schema_field = field_properties[field]
        if field == "status" and value is not None:  # default is None
            reduced_need[field] = value
        if field == "tags" and len(value) > 0:  # default is []
            reduced_need[field] = value

    return reduced_need


def get_severity(
    rule: MessageRuleEnum, user_severity: SeverityEnum | None = None
) -> SeverityEnum:
    """Get rule severity, select the default severity if not overridden by a schema."""
    if user_severity is not None:
        return user_severity
    return MAP_RULE_DEFAULT_SEVERITY[rule]


def any_not_of_rule(warnings: list[OntologyWarning], rule: MessageRuleEnum) -> bool:
    """
    Check if any warning in the list does not match the given rule.

    :param warnings: List of OntologyWarning objects.
    :param rule: The rule to check against.
    :return: True if any warning does not match the rule, False otherwise.
    """
    return any(warning["rule"] != rule for warning in warnings)


def validate_object_schema_compiles(schema: Any) -> None:
    """Validate schema properties by trying to compile them."""
    jsonschema_rs.validator_for(
        {
            "$schema": _SCHEMA_VERSION,
            "type": "object",
            **{
                k: schema[k]
                for k in ("properties", "allOf", "required", "unevaluatedProperties")
                if k in schema
            },
        },
        validate_formats=True,
        pattern_options=jsonschema_rs.RegexOptions(),
    )


@dataclass(slots=True, frozen=True)
class SchemaValidator:
    raw: NeedFieldsSchemaWithVersionType
    compiled: Validator
    properties: set[str]


def compile_validator(schema: NeedFieldsSchemaType) -> SchemaValidator:
    """Compile a JSON schema into a validator."""
    final_schema: NeedFieldsSchemaWithVersionType = {
        "$schema": _SCHEMA_VERSION,
        "type": "object",
        **{  # type: ignore[typeddict-item]
            k: schema[k]  # type: ignore[literal-required]
            for k in ("properties", "allOf", "required", "unevaluatedProperties")
            if k in schema
        },
    }
    properties = get_properties_from_schema(final_schema)
    compiled = jsonschema_rs.validator_for(
        cast(dict[str, Any], final_schema),
        validate_formats=True,
        pattern_options=RegexOptions(),
    )
    return SchemaValidator(raw=final_schema, compiled=compiled, properties=properties)


def get_ontology_warnings(
    need: NeedItem,
    field_properties: Mapping[str, NeedFieldProperties],
    validator: SchemaValidator,
    fail_rule: MessageRuleEnum,
    success_rule: MessageRuleEnum,
    schema_path: list[str],
    need_path: list[str],
    user_message: str | None = None,
    user_severity: SeverityEnum | None = None,
) -> list[OntologyWarning]:
    reduced_need = reduce_need(need, field_properties, validator.properties)
    warnings: list[OntologyWarning] = []
    warning: OntologyWarning
    try:
        validation_errors: list[ValidationError] = list(
            validator.compiled.iter_errors(instance=reduced_need)
        )
    except ValidationError as exc:
        warning = {
            "rule": MessageRuleEnum.cfg_schema_error,
            "severity": get_severity(MessageRuleEnum.cfg_schema_error),
            "validation_message": str(exc),
            "need": need,
            "schema_path": schema_path,
            "need_path": [need["id"]],
        }
        if user_message is not None:
            warning["user_message"] = user_message
        warnings.append(warning)
        return warnings

    if validation_errors:
        for err in validation_errors:
            warning = {
                "rule": fail_rule,
                "severity": get_severity(fail_rule, user_severity),
                "validation_message": err.message,
                "need": need,
                "reduced_need": reduced_need,
                "final_schema": validator.raw,
                "schema_path": [*schema_path, *(str(item) for item in err.schema_path)],
                "need_path": need_path,
            }
            if field := ".".join([str(x) for x in err.instance_path]):
                warning["field"] = field
            if user_message is not None:
                warning["user_message"] = user_message
            warnings.append(warning)
            return warnings
    else:
        warning = {
            "rule": success_rule,
            "severity": get_severity(success_rule),
            "need": need,
            "reduced_need": reduced_need,
            "final_schema": validator.raw,
            "schema_path": schema_path,
            "need_path": need_path,
        }
        if user_message is not None:
            warning["user_message"] = user_message
        warnings.append(warning)
    return warnings
