"""SN extension for schema validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final, TypedDict, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

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
)
from sphinx_needs.schema.config_utils import get_schema_name
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


def validate_need(
    config: NeedsSphinxConfig,
    need: NeedItem,
    needs: NeedsView,
    field_properties: Mapping[str, NeedFieldProperties],
    extra_option_schemas: NeedFieldsSchemaType,
    extra_link_schemas: NeedFieldsSchemaType,
    type_schemas: Sequence[SchemasRootType],
) -> list[OntologyWarning]:
    """
    Validate a single need against all extra option, link option and type schemas.

    The loop creates reports of type ReportSingleType that follow the schema
    definition structure. The reports are then converted to
    NestedWarningType objects presented to the user.
    """
    all_warnings: list[OntologyWarning] = []

    if extra_option_schemas.get("properties"):
        # check schemas of extra options and extra links for the need
        new_warnings_options = get_ontology_warnings(
            need,
            field_properties,
            extra_option_schemas,
            fail_rule=MessageRuleEnum.extra_option_fail,
            success_rule=MessageRuleEnum.extra_option_success,
            schema_path=["extra_options", "schema"],
            need_path=[need["id"]],
        )
        save_debug_files(config, new_warnings_options)
        all_warnings.extend(new_warnings_options)

    if extra_link_schemas.get("properties"):
        new_warnings_links = get_ontology_warnings(
            need,
            field_properties,
            extra_link_schemas,
            fail_rule=MessageRuleEnum.extra_link_fail,
            success_rule=MessageRuleEnum.extra_link_success,
            schema_path=["extra_links", "schema"],
            need_path=[need["id"]],
        )
        save_debug_files(config, new_warnings_links)
        all_warnings.extend(new_warnings_links)

    for type_schema in type_schemas:
        # maintain state for nested network validation
        schema_name = get_schema_name(type_schema)
        if type_schema.get("select"):
            new_warnings_select = get_ontology_warnings(
                need,
                field_properties,
                cast(NeedFieldsSchemaType, type_schema["select"]),
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

        user_severity = (
            SeverityEnum[type_schema["severity"]] if "severity" in type_schema else None
        )
        local_network_schema: ValidateSchemaType = {}
        if "local" in type_schema["validate"]:
            local_network_schema["local"] = type_schema["validate"]["local"]
        if "network" in type_schema["validate"]:
            local_network_schema["network"] = type_schema["validate"]["network"]
        _, new_warnings_recurse = recurse_validate_schemas(
            config,
            need,
            needs,
            user_message=type_schema.get("message"),
            field_properties=field_properties,
            schema=local_network_schema,
            severity=user_severity,
            schema_path=[schema_name],
            need_path=[need["id"]],
            recurse_level=0,
        )
        all_warnings.extend(new_warnings_recurse)

    return all_warnings


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
        warnings_local = get_ontology_warnings(
            need,
            field_properties,
            cast(NeedFieldsSchemaType, schema["local"]),  # refs were replaced already
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
    json_schema: NeedFieldsSchemaWithVersionType,
) -> dict[str, Any]:
    """
    Reduce a need to its relevant fields for validation in a specific schema context.

    The reduction is required to separated actively set fields from defaults.
    Also internal fields shall be removed, if they are not actively used in the schema.
    This is required to make unevaluatedProperties work as expected which disallows
    additional fields.

    Needs can be reduced in multiple contexts as the need can be primary target of validation
    or it can be a link target which might mean only a single field shall be checked for a
    specific value.

    Fields are kept
    - if they are extra fields and differ from their default value
    - if they are links and the list is not empty
    - if they are part of the user provided schema

    The function coerces extra option strings to their specified JSON schema types:
    -> integer -> int
    -> number -> float
    -> boolean -> bool

    :param need: The need to reduce.
    :param json_schema: The user provided and merged JSON merge.
    """
    reduced_need: dict[str, Any] = {}
    schema_properties = get_properties_from_schema(json_schema)
    for field, value in need.items():
        keep = False
        schema_field = field_properties[field]

        if schema_field["field_type"] == "extra" and not (
            "default" in schema_field and value == schema_field["default"]
        ):
            # keep explicitly set extra options
            keep = True

        if schema_field["field_type"] == "links" and value:
            # keep non-empty link fields
            keep = True

        if (
            schema_field["field_type"] == "core"
            and field in schema_properties
            and not ("default" in schema_field and value == schema_field["default"])
        ):
            # keep core field, it has no default or differs from the default and
            # is part of the user provided schema
            keep = True

        if value is None:
            # value is not provided
            keep = False

        if keep:
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


def get_ontology_warnings(
    need: NeedItem,
    field_properties: Mapping[str, NeedFieldProperties],
    schema: NeedFieldsSchemaType,
    fail_rule: MessageRuleEnum,
    success_rule: MessageRuleEnum,
    schema_path: list[str],
    need_path: list[str],
    user_message: str | None = None,
    user_severity: SeverityEnum | None = None,
) -> list[OntologyWarning]:
    final_schema: NeedFieldsSchemaWithVersionType = {
        "$schema": _SCHEMA_VERSION,
        "type": "object",
        **{  # type: ignore[typeddict-item]
            k: schema[k]  # type: ignore[literal-required]
            for k in ("properties", "allOf", "required", "unevaluatedProperties")
            if k in schema
        },
    }
    validator = Draft202012Validator(final_schema, format_checker=FormatChecker())
    reduced_need = reduce_need(need, field_properties, final_schema)
    warnings: list[OntologyWarning] = []
    warning: OntologyWarning
    try:
        validation_errors: list[ValidationError] = list(
            validator.iter_errors(instance=reduced_need)
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
                "final_schema": final_schema,
                "schema_path": [*schema_path, *(str(item) for item in err.schema_path)],
                "need_path": need_path,
                "field": ".".join([str(x) for x in err.path]),
            }
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
            "final_schema": final_schema,
            "schema_path": schema_path,
            "need_path": need_path,
        }
        if user_message is not None:
            warning["user_message"] = user_message
        warnings.append(warning)
    return warnings
