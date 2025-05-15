"""SN extension for schema validation."""

import copy
from enum import Enum
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.schema.config import (
    MAP_RULE_SEVERITY,
    MessageRuleEnum,
    SchemaType,
    SeverityEnum,
)
from sphinx_needs.schema.reporting import (
    OntologyWarning,
    report_message,
)
from sphinx_needs.schema.utils import get_properties_from_schema
from sphinx_needs.views import NeedsView

# TODO: error for conflicting unevaluatedProperties
# TODO: schema registry
# TODO: read needs from index / json
# TODO: config from toml
# TODO: trigger-schema and trigger-schema-id cannot coexist


_schema_version = {"$schema": "https://json-schema.org/draft/2020-12/schema"}
"""
JSON schema metaversion to use.

The implementation requires at least draft 2019-09 as unevaluatedProperties was added there.
"""

_base_schema: dict[str, Any] = {}
"""
Combined static schema information for options and links.

This is valid for all need types and conditions.
"""

_needs_schema: dict[str, Any] = {}
"""The needs schema as it would be written to needs.json."""


def merge_static_schemas(config: NeedsSphinxConfig) -> bool:
    """
    Merge needs_schema_options and needs_schema_links per need.

    Writes to the global variable _base_schema.
    """
    any_found = False
    for name, option in config.extra_options.items():
        if option.schema is not None:
            any_found = True
            _base_schema.update({name: option.schema})
    for link in config.extra_links:
        if link.get("schema") is not None:
            any_found = True
            _base_schema.update({link["option"]: link["schema"]})
    return any_found


def reduce_need(
    config: NeedsSphinxConfig,
    need: dict[str, Any],
    json_schema: dict[str, Any],
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
    :raises ValueError: If a field cannot be coerced to its specified type.
    """
    reduced_need: dict[str, Any] = {}
    schema_properties = get_properties_from_schema(json_schema)
    for field, value in need.items():
        keep = False
        schema_field = _needs_schema[field]

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

        if keep:
            coerced_value = value
            if schema_field["field_type"] == "extra" and field in config.extra_options:
                option_schema = config.extra_options[field].schema
                if (
                    option_schema is not None
                    and "type" in option_schema
                    and option_schema["type"] != "string"
                ):
                    type_ = option_schema["type"]
                    if not isinstance(value, str):
                        raise ValueError(
                            f"Field '{field}': cannot coerce '{value}' (type: {type(value)}) to {type_}"
                        )
                    try:
                        if type_ == "integer":
                            coerced_value = int(value)
                        elif type_ == "number":
                            coerced_value = float(value)
                    except ValueError as exc:
                        raise ValueError(
                            f"Field '{field}': cannot coerce '{value}' to {type_}"
                        ) from exc
                    if type_ == "boolean":
                        truthy = {"true", "yes", "y", "on", "1"}
                        falsy = {"false", "no", "n", "off", "0"}
                        if value.lower() in truthy:
                            coerced_value = True
                        elif value.lower() in falsy:
                            coerced_value = False
                        else:
                            raise ValueError(
                                f"Field '{field}': cannot coerce '{value}' to boolean"
                            )
            reduced_need[field] = coerced_value

    return reduced_need


def get_localschema_errors(
    need: dict[str, Any], schema: dict[str, Any]
) -> list[ValidationError]:
    """
    Validate a need against a schema and return a list of errors.

    :raises jsonschema_rs.ValidationError: If the schema is invalid cannot be built.
    """
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return list(validator.iter_errors(instance=need))


def get_schema_by_id(schema_id: str, schemas: list[SchemaType]) -> SchemaType:
    """
    Resolve a schema reference by its ID.

    :param schema_id: The ID of the schema to resolve.
    :param schemas: The list of schemas to search in.
    """
    for schema in schemas:
        if schema.get("id") == schema_id:
            return schema
    raise ValueError(f"Cannot resolve schema-id '{schema_id}'")


class ContextEnum(Enum):
    """Validation context when recursively calling validate_need."""

    PRIMARY = "primary"
    """Validation happens on the primary need (non-recursively)."""
    NESTED = "nesteNeedsViewd"
    """Validation happens along the path of a trigger or link schema."""


def validate_need(
    config: NeedsSphinxConfig,
    need: dict[str, Any],
    needs: NeedsView,
    all_type_schemas: list[SchemaType],
    type_schemas: list[SchemaType],
    need_path: list[str],
    schema_path: list[str],
    context: ContextEnum,
) -> list[OntologyWarning]:
    warnings: list[OntologyWarning] = []

    # construct root schema for the validation
    final_localschema: dict[str, Any] = {
        **_schema_version,
        "type": "object",
        "properties": {
            **_base_schema,
        },
    }
    all_of = []
    picked_schema_idxs = []
    for type_schema in type_schemas:
        idx = type_schema["idx"]
        schema_path_new = [
            *schema_path,
            f"{type_schema['id']}[{idx}]" if "id" in type_schema else f"[{idx}]",
        ]
        if type_schema.get("dependency", False) and context == ContextEnum.PRIMARY:
            # no primary validation if a type schema is marked as dependency;
            # however if the function is called recursively in a trigger context originating
            # from trigger_schema_id, the validation shall *not* be skipped
            report_message(
                config=config,
                warnings=warnings,
                need=need,
                schema=final_localschema,
                rule=MessageRuleEnum.skipped_dependency,
                need_path=need_path,
                schema_path=schema_path_new,
            )
            continue

        # only check types field if it is given and not empty
        if (
            "types" in type_schema
            and type_schema["types"]
            and need["type"] not in type_schema["types"]
        ):
            # Type validation behaves differently for primary and trigger validation:
            # For primary validation, the types field is an allow list,
            # non-matching types will just be skipped.
            # For nested (trigger/link) validation, the types field is a deny list,
            # non-matching types will cause a validation error.
            if context == ContextEnum.PRIMARY:
                report_message(
                    config=config,
                    warnings=warnings,
                    need=need,
                    schema=final_localschema,
                    rule=MessageRuleEnum.skipped_wrong_type,
                    need_path=need_path,
                    schema_path=schema_path_new,
                )
                continue
            if context == ContextEnum.NESTED:
                validation_msg = (
                    f"Need '{need['id']}' has type '{need['type']}' but is not"
                    f" of any of the expected types: {type_schema['types']}"
                )
                report_message(
                    config=config,
                    warnings=warnings,
                    need=need,
                    schema=final_localschema,
                    rule=MessageRuleEnum.wrong_type,
                    need_path=need_path,
                    schema_path=schema_path_new,
                    validation_msg=validation_msg,
                )
                return warnings

        if type_schema.get("trigger_schema"):
            # the trigger-schema is evaluated in the local context, so
            # replace local-schema with trigger-schema in a new instance
            trigger_schema = copy.deepcopy(type_schema)
            trigger_schema["local_schema"] = trigger_schema.pop("trigger_schema")

            warnings_local = validate_need(
                config=config,
                need=need,
                needs=needs,
                all_type_schemas=all_type_schemas,
                type_schemas=[trigger_schema],
                need_path=need_path,
                schema_path=[*schema_path_new, "trigger_schema"],
                context=ContextEnum.NESTED,
            )
            if warnings_local:
                if any(
                    MAP_RULE_SEVERITY[warning["rule"]] == SeverityEnum.config_error
                    for warning in warnings_local
                ):
                    # user config error, abort the validation
                    warnings.extend(warnings_local)
                    return warnings

                if context == ContextEnum.PRIMARY:
                    # local trigger unsuccessful, skip this schema type
                    continue
                else:
                    # nested validation, fail the validation
                    warnings.extend(warnings_local)
                    return warnings

        if type_schema.get("trigger_schema_id"):
            trigger_schema = get_schema_by_id(
                type_schema["trigger_schema_id"], all_type_schemas
            )

            warnings_local = validate_need(
                config=config,
                need=need,
                needs=needs,
                all_type_schemas=all_type_schemas,
                type_schemas=[trigger_schema],
                need_path=need_path,
                schema_path=[
                    *schema_path_new,
                    f"trigger_schema_id[{type_schema['trigger_schema_id']}]",
                ],
                context=ContextEnum.NESTED,
            )
            if warnings_local:
                if any(
                    MAP_RULE_SEVERITY[warning["rule"]] == SeverityEnum.config_error
                    for warning in warnings_local
                ):
                    # user config error, abort the validation
                    warnings.extend(warnings_local)
                    return warnings

                if context == ContextEnum.PRIMARY:
                    # local trigger unsuccessful, skip this schema type
                    continue
                else:
                    # nested validation, fail the validation
                    warnings.extend(warnings_local)
                    return warnings

        if type_schema.get("link_schema"):
            for link_type, link_schema in type_schema["link_schema"].items():
                if link_schema.get("schema_id"):
                    linked_schema = get_schema_by_id(
                        link_schema["schema_id"], all_type_schemas
                    )
                    needs_matching: list[str] = []
                    needs_mismatching: list[str] = []
                    if need[link_type]:
                        for link in need[link_type]:
                            target_need = needs.get(link)
                            if target_need is None:
                                msg = (
                                    f"Need '{need['id']}' has link type '{link_type}'"
                                    f" with invalid target need '{link}'."
                                )
                                report_message(
                                    config=config,
                                    warnings=warnings,
                                    need=need,
                                    schema=dict(linked_schema),
                                    rule=MessageRuleEnum.missing_target,
                                    need_path=[*need_path, link_type],
                                    schema_path=[
                                        *schema_path_new,
                                        "link_schema",
                                        link_type,
                                        f"schema_id[{link_schema['schema_id']}]",
                                    ],
                                    validation_msg=msg,
                                    field=link_type,
                                )
                                continue
                            target_need_dict = dict(target_need)
                            new_schema_path = copy.deepcopy(schema_path)
                            new_schema_path.append(
                                f"{idx}[{linked_schema['id']}]"
                                if "id" in linked_schema
                                else str(idx)
                            )
                            schema_path.append(
                                f"{idx}[{type_schema['id']}]"
                                if "id" in type_schema
                                else str(idx)
                            )
                            ontology_warnings = validate_need(
                                config=config,
                                need=target_need_dict,
                                needs=needs,
                                all_type_schemas=all_type_schemas,
                                type_schemas=[cast(SchemaType, linked_schema)],
                                need_path=[
                                    *need_path,
                                    link_type,
                                    str(target_need_dict["id"]),
                                ],
                                schema_path=[
                                    *schema_path_new,
                                    "link_schema",
                                    link_type,
                                ],
                                context=ContextEnum.NESTED,
                            )
                            if ontology_warnings:
                                if any(
                                    MAP_RULE_SEVERITY[warning["rule"]]
                                    == SeverityEnum.config_error
                                    for warning in ontology_warnings
                                ):
                                    # user config error, abort the validation
                                    warnings.extend(ontology_warnings)
                                    return warnings
                                needs_mismatching.append(str(target_need_dict["id"]))
                            else:
                                needs_matching.append(str(target_need_dict["id"]))
                    cnt_matching = len(needs_matching)
                    cnt_mismatching = len(needs_mismatching)
                    if (
                        "minItems" in link_schema
                        and cnt_matching < link_schema["minItems"]
                    ):
                        msg = (
                            "Too few valid links of type"
                            f" '{link_type}' ({cnt_matching} <"
                            f" {link_schema['minItems']})"
                        )

                        if needs_matching:
                            msg += f" / ok: {','.join(needs_matching)}"
                        if needs_mismatching:
                            msg += f" / nok: {','.join(needs_mismatching)}"
                        report_message(
                            config=config,
                            warnings=warnings,
                            need=need,
                            schema=dict(linked_schema),
                            rule=MessageRuleEnum.too_few_links,
                            need_path=[*need_path, link_type],
                            schema_path=[
                                *schema_path_new,
                                "link_schema",
                                link_type,
                                f"schema_id[{link_schema['schema_id']}]",
                            ],
                            validation_msg=msg,
                            field=link_type,
                        )
                    if (
                        "maxItems" in link_schema
                        and cnt_matching > link_schema["maxItems"]
                    ):
                        msg = (
                            f"Need '{need['id']}' has too many valid links of type"
                            f" '{link_type}' ({cnt_matching} >"
                            f" {link_schema['maxItems']})."
                        )
                        report_message(
                            config=config,
                            warnings=warnings,
                            need=need,
                            schema=dict(linked_schema),
                            rule=MessageRuleEnum.too_many_links,
                            need_path=[*need_path, link_type],
                            schema_path=[
                                *schema_path_new,
                                "link_schema",
                                link_type,
                                f"schema_id[{link_schema['schema_id']}]",
                            ],
                            validation_msg=msg,
                            field=link_type,
                        )
                    if (
                        not link_schema.get("unevaluatedItems", True)
                        and cnt_mismatching > 0
                    ):
                        msg = f"{cnt_mismatching} invalid links of type '{link_type}'"
                        msg += f" / nok: {','.join(needs_mismatching)}"
                        report_message(
                            config=config,
                            warnings=warnings,
                            need=need,
                            schema=dict(linked_schema),
                            rule=MessageRuleEnum.unevaluated_additional_links,
                            need_path=[*need_path, link_type],
                            schema_path=[
                                *schema_path_new,
                                "link_schema",
                                link_type,
                            ],
                            validation_msg=msg,
                            field=link_type,
                        )
                else:
                    # link schema without schema_id, just count links
                    cnt_matching = len(need[link_type])
                    if (
                        "minItems" in link_schema
                        and cnt_matching < link_schema["minItems"]
                    ):
                        msg = (
                            f"Need '{need['id']}' has too few links of type"
                            f" '{link_type}' ({cnt_matching} <"
                            f" {link_schema['minItems']})"
                        )
                        report_message(
                            config=config,
                            warnings=warnings,
                            need=need,
                            schema=dict(type_schema),
                            rule=MessageRuleEnum.too_few_links,
                            need_path=[*need_path, link_type],
                            schema_path=[
                                *schema_path_new,
                                "link_schema",
                                link_type,
                            ],
                            validation_msg=msg,
                            field=link_type,
                        )
                    if (
                        "maxItems" in link_schema
                        and cnt_matching > link_schema["maxItems"]
                    ):
                        msg = (
                            f"Need '{need['id']}' has too many links of type"
                            f" '{link_type}' ({cnt_matching} >"
                            f" {link_schema['maxItems']})"
                        )
                        report_message(
                            config=config,
                            warnings=warnings,
                            need=need,
                            schema=dict(type_schema),
                            rule=MessageRuleEnum.too_many_links,
                            need_path=[*need_path, link_type],
                            schema_path=[
                                *schema_path_new,
                                "link_schema",
                                link_type,
                            ],
                            validation_msg=msg,
                            field=link_type,
                        )
        if type_schema.get("local_schema"):
            picked_schema_idxs.append(idx)
            all_of.append({**type_schema["local_schema"]})

    if all_of:
        final_localschema["allOf"] = all_of

    try:
        reduced_need = reduce_need(config, need, final_localschema)
    except ValueError as exc:
        report_message(
            config=config,
            warnings=warnings,
            need=need,
            schema=final_localschema,
            rule=MessageRuleEnum.option_type_error,
            need_path=need_path,
            schema_path=schema_path,
            validation_msg=str(exc),
        )
        return warnings

    try:
        validation_warnings = get_localschema_errors(reduced_need, final_localschema)
    except ValidationError as exc:
        msg = f"Error building schema for need '{need['id']}': {exc}"
        report_message(
            config=config,
            warnings=warnings,
            need=reduced_need,
            schema=final_localschema,
            rule=MessageRuleEnum.cfg_schema_error,
            need_path=need_path,
            schema_path=schema_path,
            validation_msg=msg,
        )
        # no need to extend warnings with warnings_local if schema is invalid
        return warnings

    if validation_warnings:
        rule = MessageRuleEnum.validation_fail
        for warning in validation_warnings:
            # default severity for this type of error
            # see whether a custom severity is set in case the violation originated
            # from any type schema
            severity = MAP_RULE_SEVERITY[rule]
            user_msg = None
            if warning.schema_path[0] == "allOf":
                allof_idx = int(warning.schema_path[1])
                type_schema = type_schemas[allof_idx]
                if "severity" in type_schema:
                    severity = SeverityEnum[type_schema["severity"]]
                if "message" in type_schema:
                    user_msg = type_schema["message"]

            report_message(
                config=config,
                warnings=warnings,
                need=reduced_need,
                schema=final_localschema,
                rule=rule,
                need_path=need_path,
                schema_path=[*schema_path, *[str(x) for x in warning.schema_path]],
                severity=severity,
                user_msg=user_msg,
                validation_msg=warning.message,
                field=".".join([str(x) for x in warning.path]),
            )
    else:
        picked_schemas = "".join([f"[{x}]" for x in picked_schema_idxs])
        report_message(
            config=config,
            warnings=warnings,
            need=reduced_need,
            schema=final_localschema,
            rule=MessageRuleEnum.validation_success,
            need_path=need_path,
            schema_path=[*schema_path, picked_schemas],
            severity=MAP_RULE_SEVERITY[MessageRuleEnum.validation_success],
        )

    return warnings
