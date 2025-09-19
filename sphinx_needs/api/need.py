from __future__ import annotations

import hashlib
import os
import re
import warnings
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any, TypedDict, cast

from docutils import nodes
from docutils.parsers.rst.states import RSTState
from docutils.statemachine import StringList
from jinja2 import Template
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import (
    NeedsInfoType,
    NeedsPartType,
    SphinxNeedsData,
)
from sphinx_needs.directives.needuml import Needuml, NeedumlException
from sphinx_needs.exceptions import InvalidNeedException
from sphinx_needs.filter_common import (
    PredicateContextData,
    apply_default_predicate,
)
from sphinx_needs.functions.functions import DynamicFunctionParsed
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import (
    NeedItem,
    NeedItemSourceProtocol,
    NeedItemSourceUnknown,
    NeedPartData,
    NeedsContent,
)
from sphinx_needs.needs_schema import (
    AllowedTypes,
    FieldFunctionArray,
    FieldLiteralValue,
    FieldSchema,
    FieldsSchema,
    LinkSchema,
    LinksFunctionArray,
    LinksLiteralValue,
)
from sphinx_needs.nodes import Need
from sphinx_needs.roles.need_part import find_parts, update_need_with_parts
from sphinx_needs.utils import jinja_parse
from sphinx_needs.variants import VariantFunctionParsed
from sphinx_needs.views import NeedsView

logger = get_logger(__name__)

_deprecated_kwargs = {
    "constraints_passed",
    "links_string",
    "hide_tags",
    "hide_status",
    "delete",
}


def generate_need(
    needs_config: NeedsSphinxConfig,
    needs_schema: FieldsSchema,
    need_type: str,
    title: str,
    *,
    need_source: NeedItemSourceProtocol | None = None,
    docname: None | str = None,
    lineno: None | int = None,
    id: str | None = None,
    doctype: str = ".rst",
    content: str = "",
    lineno_content: None | int = None,
    status: str | None = None,
    tags: None | str | list[str] = None,
    constraints: None | str | list[str] = None,
    parts: dict[str, NeedsPartType] | None = None,
    arch: dict[str, str] | None = None,
    signature: None | str = None,
    sections: Sequence[str] | None = None,
    jinja_content: bool | None = None,
    hide: None | bool | str = None,
    collapse: None | bool | str = None,
    style: None | str = None,
    layout: None | str = None,
    template_root: Path | None = None,
    template: None | str = None,
    pre_template: str | None = None,
    post_template: str | None = None,
    is_import: bool = False,
    is_external: bool = False,
    external_url: str | None = None,
    external_css: str = "external_link",
    full_title: str | None = None,
    **kwargs: Any,
) -> NeedItem:
    """Creates a validated need data entry, without adding it to the project.

    .. important:: This function does not parse or analyse the content,
        and so will not auto-populate the ``parts`` or ``arch`` fields of the need
        from the content.

        It will also not validate that the ID is not already in use within the project.

    :raises InvalidNeedException: If the data fails any validation issue.

    ``kwargs`` can contain options defined in ``needs_extra_options`` and ``needs_extra_links``.
    If an entry is found in ``kwargs``, which *is not* specified in the configuration or registered e.g. via
    ``add_extra_option``, an exception is raised.

    If the need is within the current project, i.e. not an external need,
    the following parameters are used to help provide source mapped warnings and errors:

    :param docname: documentation identifier, for the referencing document.
    :param lineno: line number of the top of the directive (1-indexed).
    :param lineno_content: line number of the content start of the directive (1-indexed).

    Otherwise, the following parameters are used:

    :param is_external: Is true, no node is created and need is referencing external url
    :param external_url: URL as string, which is used as target if ``is_external`` is ``True``
    :param external_css: CSS class name as string, which is set for the <a> tag.

    Additional parameters:

    :param app: Sphinx application object.
    :param state: Current state object.
    :param need_type: Name of the need type to create.
    :param title: String as title.
    :param full_title: This is given, if an auto-generated title was trimmed.
        It is used to auto-generate the ID, if required.
    :param id: ID as string. If not given, an id will get generated.
    :param content: Content of the need
    :param status: Status as string.
    :param tags: A list of tags, or a comma separated string.
    :param constraints: Constraints as single, comma separated, string.
    :param constraints_passed: Contains bool describing if all constraints have passed
    :param hide: If True then the need is not rendered.
        ``None`` means that the value can be overriden by global defaults, else it is set to False.
    :param collapse: If True, then hide the meta-data information of the need.
        ``None`` means that the value can be overriden by global defaults, else it is set to False.
    :param style: String value of class attribute of node.
    :param layout: String value of layout definition to use
    :param template_root: Root path for template files, only required if the template_path config is relative.
    :param template: Template name to use for the content of this need
    :param pre_template: Template name to use for content added before need
    :param post_template: Template name to use for the content added after need
    """
    source = (
        NeedItemSourceUnknown(
            docname=docname,
            lineno=lineno,
            lineno_content=lineno_content,
            is_import=is_import,
            is_external=is_external,
            external_url=external_url if is_external else None,
        )
        if need_source is None
        else need_source
    )

    # location is used to provide source mapped warnings
    location = (
        (source.dict_repr["docname"], source.dict_repr["lineno"])
        if source.dict_repr["docname"]
        else None
    )

    # validate kwargs
    allowed_kwargs = {x["option"] for x in needs_config.extra_links} | set(
        needs_config.extra_options
    )
    unknown_kwargs = set(kwargs) - allowed_kwargs
    if unknown_kwargs:
        raise InvalidNeedException(
            "invalid_kwargs",
            f"Options {unknown_kwargs!r} not in 'needs_extra_options' or 'needs_extra_links.",
        )

    # get the need type data
    configured_need_types = {ntype["directive"]: ntype for ntype in needs_config.types}
    if not (need_type_data := configured_need_types.get(need_type)):
        raise InvalidNeedException("invalid_type", f"Unknown need type {need_type!r}.")

    # generate and validate the id
    if id is None and needs_config.id_required:
        raise InvalidNeedException(
            "missing_id", "No ID defined, but 'needs_id_required' is set to True."
        )
    need_id = (
        _make_hashed_id(
            need_type_data["prefix"],
            title if full_title is None else full_title,
            content,
            needs_config,
        )
        if id is None
        else id
    )
    if (
        needs_config.id_regex
        and not is_external
        and not re.match(needs_config.id_regex, need_id)
    ):
        raise InvalidNeedException(
            "invalid_id",
            f"Given ID {need_id!r} does not match configured regex {needs_config.id_regex!r}",
        )

    # TODO allow this to be configurable, for if external/import source
    allow_coercion = True

    title_converted = _convert_type_core("title", title, needs_schema, allow_coercion)
    status_converted = _convert_type_core(
        "status", status, needs_schema, allow_coercion
    )
    tags_converted = _convert_type_core("tags", tags, needs_schema, allow_coercion)
    constraints_converted = _convert_type_core(
        "constraints", constraints, needs_schema, allow_coercion
    )
    layout_converted = _convert_type_core(
        "layout", layout, needs_schema, allow_coercion
    )
    style_converted = _convert_type_core("style", style, needs_schema, allow_coercion)
    hide_converted = _convert_type_core("hide", hide, needs_schema, allow_coercion)
    collapse_converted = _convert_type_core(
        "collapse", collapse, needs_schema, allow_coercion
    )
    template_converted = _convert_type_core(
        "template", template, needs_schema, allow_coercion
    )
    pre_template_converted = _convert_type_core(
        "pre_template", pre_template, needs_schema, allow_coercion
    )
    post_template_converted = _convert_type_core(
        "post_template", post_template, needs_schema, allow_coercion
    )

    if (
        needs_config.statuses
        and isinstance(status_converted, FieldLiteralValue)
        and status_converted.value
        not in [stat["name"] for stat in needs_config.statuses]
    ):
        # TODO this check should be later in processing, once we have resolved any dynamic functions
        raise InvalidNeedException(
            "invalid_status",
            f"Status {status_converted.value!r} not in 'needs_statuses'.",
        )

    if (
        needs_config.tags
        and isinstance(tags_converted, FieldLiteralValue)
        and isinstance(tags_converted.value, Iterable)
        and (
            unknown_tags := set(tags_converted.value)
            - {t["name"] for t in needs_config.tags}
        )
    ):
        # TODO this check should be later in processing, once we have resolved any dynamic functions
        raise InvalidNeedException(
            "invalid_tags", f"Tags {unknown_tags!r} not in 'needs_tags'."
        )

    if (
        isinstance(constraints_converted, FieldLiteralValue)
        and isinstance(constraints_converted.value, Iterable)
        and (
            unknown_constraints := set(constraints_converted.value)
            - set(needs_config.constraints)
        )
    ):
        # TODO this check should be later in processing, once we have resolved any dynamic functions
        raise InvalidNeedException(
            "invalid_constraints",
            f"Constraints {unknown_constraints!r} not in 'needs_constraints'.",
        )

    extras_no_defaults: dict[str, None | FieldLiteralValue | FieldFunctionArray] = {}
    for extra_field in needs_schema.iter_extra_fields():
        if extra_field.name not in kwargs:
            extras_no_defaults[extra_field.name] = None
        else:
            try:
                extras_no_defaults[extra_field.name] = (
                    None
                    if kwargs[extra_field.name] is None
                    else extra_field.convert_or_type_check(
                        kwargs[extra_field.name], allow_coercion=allow_coercion
                    )
                )
            except Exception as err:
                raise InvalidNeedException(
                    "invalid_extra_option",
                    f"Extra option {extra_field.name!r} is invalid: {err}",
                ) from err

    links_no_defaults: dict[str, None | LinksLiteralValue | LinksFunctionArray] = {}
    for link_field in needs_schema.iter_link_fields():
        if link_field.name not in kwargs:
            links_no_defaults[link_field.name] = None
        else:
            try:
                links_no_defaults[link_field.name] = (
                    None
                    if kwargs[link_field.name] is None
                    else link_field.convert_or_type_check(
                        kwargs[link_field.name], allow_coercion=allow_coercion
                    )
                )
            except Exception as err:
                raise InvalidNeedException(
                    "invalid_link_option",
                    f"Link option {link_field.name!r} is invalid: {err}",
                ) from err

    defaults_ctx: PredicateContextData = {
        "id": need_id,
        "type": need_type,
        "title": title_converted.value  # type: ignore[typeddict-item]
        if isinstance(title_converted, FieldLiteralValue)
        else "",
        "tags": copy(tags_converted.value)  # type: ignore[arg-type]
        if isinstance(tags_converted, FieldLiteralValue)
        else [],  # TODO allow for non-df/vf values?
        "status": status_converted.value  # type: ignore[typeddict-item]
        if isinstance(status_converted, FieldLiteralValue)
        else None,
        "docname": source.dict_repr["docname"],
        "is_import": source.dict_repr["is_import"],
        "is_external": source.dict_repr["is_external"],
    }
    defaults_extras_ctx = {
        k: copy(v.value) if isinstance(v, FieldLiteralValue) else None
        for k, v in extras_no_defaults.items()
    }
    defaults_links_ctx = {
        k: copy(v.value) if isinstance(v, LinksLiteralValue) else []
        for k, v in links_no_defaults.items()
    }

    context: DefaultContextData = {
        "config": needs_config,
        "core": defaults_ctx,
        "extras": defaults_extras_ctx,
        "links": defaults_links_ctx,
    }

    status_converted = (
        status_converted
        if status_converted is not None
        else _get_field_default(needs_schema.get_core_field("status"), **context)
    )
    tags_converted = (
        tags_converted
        if tags_converted is not None
        else _get_field_default(needs_schema.get_core_field("tags"), **context)
    )
    collapse_converted = (
        collapse_converted
        if collapse_converted is not None
        else _get_field_default(needs_schema.get_core_field("collapse"), **context)
    )
    hide_converted = (
        hide_converted
        if hide_converted is not None
        else _get_field_default(needs_schema.get_core_field("hide"), **context)
    )
    constraints_converted = (
        constraints_converted
        if constraints_converted is not None
        else _get_field_default(needs_schema.get_core_field("constraints"), **context)
    )
    layout_converted = (
        layout_converted
        if layout_converted is not None
        else _get_field_default(needs_schema.get_core_field("layout"), **context)
    )
    style_converted = (
        style_converted
        if style_converted is not None
        else _get_field_default(needs_schema.get_core_field("style"), **context)
    )
    template_converted = (
        template_converted
        if template_converted is not None
        else _get_field_default(needs_schema.get_core_field("template"), **context)
    )
    pre_template_converted = (
        pre_template_converted
        if pre_template_converted is not None
        else _get_field_default(needs_schema.get_core_field("pre_template"), **context)
    )
    post_template_converted = (
        post_template_converted
        if post_template_converted is not None
        else _get_field_default(needs_schema.get_core_field("post_template"), **context)
    )
    extras = {
        k: _get_field_default(needs_schema.get_extra_field(k), **context)
        if v is None
        else v
        for k, v in extras_no_defaults.items()
    }
    links = {
        k: _get_links_default(needs_schema.get_link_field(k), **context)
        if v is None
        else v
        for k, v in links_no_defaults.items()
    }
    _copy_links(links, needs_config)

    title, title_func = _convert_to_str_func("title", title_converted)
    status, status_func = _convert_to_none_str_func("status", status_converted)
    tags, tags_func = _convert_to_list_str_func("tags", tags_converted)
    constraints, constraints_func = _convert_to_list_str_func(
        "constraints", constraints_converted
    )
    collapse, collapse_func = _convert_to_bool_func("collapse", collapse_converted)
    hide, hide_func = _convert_to_bool_func("hide", hide_converted)
    layout, layout_func = _convert_to_none_str_func("layout", layout_converted)
    style, style_func = _convert_to_none_str_func("style", style_converted)

    dynamic_fields: dict[str, FieldFunctionArray | LinksFunctionArray] = {}
    if title_func:
        dynamic_fields["title"] = title_func
    if status_func:
        dynamic_fields["status"] = status_func
    if tags_func:
        dynamic_fields["tags"] = tags_func
    if constraints_func:
        dynamic_fields["constraints"] = constraints_func
    if collapse_func:
        dynamic_fields["collapse"] = collapse_func
    if hide_func:
        dynamic_fields["hide"] = hide_func
    if layout_func:
        dynamic_fields["layout"] = layout_func
    if style_func:
        dynamic_fields["style"] = style_func

    # Add the need and all needed information
    core_data: NeedsInfoType = {
        "id": need_id,
        "type": need_type,
        "type_name": need_type_data["title"],
        "type_prefix": need_type_data["prefix"],
        "type_color": need_type_data.get("color") or "#000000",
        "type_style": need_type_data.get("style") or "node",
        "title": title,
        "status": status,
        "tags": tags,
        "constraints": tuple(constraints),
        "collapse": collapse,
        "hide": hide,
        "style": style,
        "layout": layout,
        "external_css": external_css or "external_link",
        "arch": arch or {},
        "has_dead_links": False,
        "has_forbidden_dead_links": False,
        "sections": tuple(sections or ()),
        "signature": signature,
    }

    template = _convert_to_str_none("template", template_converted)
    pre_template = _convert_to_str_none("pre_template", pre_template_converted)
    post_template = _convert_to_str_none("post_template", post_template_converted)
    content_info = NeedsContent(
        doctype=doctype,
        content=content,
        pre_content=None,
        post_content=None,
        template=template,
        pre_template=pre_template,
        post_template=post_template,
        jinja_content=jinja_content or False,
    )

    parts_objects = []
    for part_id, part_data in (parts or {}).items():
        if unknown_part_keys := set(part_data) - (
            {"id", "content"} | {k + "_back" for k in links}
        ):
            log_warning(
                logger,
                f"Unused keys {sorted(unknown_part_keys)} in part {part_id!r} of need {need_id!r}.",
                "part",
                location,
            )
        parts_objects.append(
            NeedPartData(id=part_id, content=str(part_data.get("content", "")))
        )

    extras_pre: dict[str, AllowedTypes | None] = {}
    for k, v in extras.items():
        if (extra_schema := needs_schema.get_extra_field(k)) is None:
            raise InvalidNeedException(
                "invalid_extra_option",
                f"Extra option {k!r} not in 'needs_extra_options'.",
            )
        if v is None:
            if not extra_schema.nullable:
                raise InvalidNeedException(
                    "invalid_extra_option",
                    f"Extra option {k!r} is not nullable, but no value or default was given.",
                )
            extras_pre[k] = None
        elif isinstance(v, FieldLiteralValue):
            extras_pre[k] = v.value
        elif isinstance(v, FieldFunctionArray):
            dynamic_fields[k] = v
            match extra_schema.type:
                case "string":
                    extras_pre[k] = ""
                case "boolean":
                    extras_pre[k] = False
                case "integer":
                    extras_pre[k] = 0
                case "number":
                    extras_pre[k] = 0.0
                case "array":
                    extras_pre[k] = []
                case other:
                    raise InvalidNeedException(
                        "invalid_extra_option",
                        f"Extra option {k!r} has unknown type {other!r}.",
                    )
        else:
            raise InvalidNeedException(
                "invalid_extra_option",
                f"Extra option {k!r} has unknown value {v!r}.",
            )

    links_pre: dict[str, list[str]] = {}
    for lk, lv in links.items():
        if lv is None:
            # TODO currently no link_schema.nullable
            raise InvalidNeedException(
                "invalid_link_option",
                f"Link option {lk!r} is not nullable, but no value or default was given.",
            )
        elif isinstance(lv, LinksLiteralValue):
            links_pre[lk] = lv.value
        elif isinstance(lv, LinksFunctionArray):
            dynamic_fields[lk] = lv
            links_pre[lk] = []
        else:
            raise InvalidNeedException(
                "invalid_link_option",
                f"Link option {lk!r} has unknown value {lv!r}.",
            )

    try:
        needs_info = NeedItem(
            core=core_data,
            extras=extras_pre,
            links=links_pre,
            source=source,
            content=content_info,
            parts=parts_objects,
            dynamic_fields=dynamic_fields,
            _validate=False,
        )
    except ValueError as err:
        raise InvalidNeedException("failed_init", str(err)) from err

    if jinja_content or template or pre_template or post_template:
        # TODO ideally perform all these content alterations before creating the need item
        if jinja_content:
            need_content_context: dict[str, Any] = {**needs_info}
            need_content_context.update(**needs_config.filter_data)
            need_content_context.update(**needs_config.render_context)
            try:
                content_info = replace(
                    content_info,
                    content=jinja_parse(need_content_context, needs_info["content"]),
                )
            except Exception as e:
                raise InvalidNeedException(
                    "invalid_jinja_content",
                    f"Error while rendering content: {e}",
                )

        if template:
            # TODO should warn if content is not empty?
            content_info = replace(
                content_info,
                content=_prepare_template(
                    needs_config, needs_info, template, template_root
                ),
            )

        if pre_template:
            content_info = replace(
                content_info,
                pre_content=_prepare_template(
                    needs_config, needs_info, pre_template, template_root
                ),
            )

        if post_template:
            content_info = replace(
                content_info,
                post_content=_prepare_template(
                    needs_config, needs_info, post_template, template_root
                ),
            )

        needs_info.set_content(content_info)

    return needs_info


def _convert_type_core(
    name: str, value: Any, schema: FieldsSchema, allow_coercion: bool
) -> FieldLiteralValue | FieldFunctionArray | None:
    try:
        field_schema = schema.get_core_field(name)
        assert field_schema is not None, f"{name} field schema does not exist"
        return (
            None
            if value is None
            else field_schema.convert_or_type_check(
                value, allow_coercion=allow_coercion
            )
        )
    except Exception as err:
        raise InvalidNeedException(
            "invalid_value", f"{name!r} value is invalid: {err}"
        ) from err


def _convert_to_str_none(
    name: str, converted: FieldLiteralValue | FieldFunctionArray | None
) -> str | None:
    if converted is None:
        return None
    elif isinstance(converted, FieldLiteralValue) and isinstance(converted.value, str):
        return converted.value
    else:
        raise InvalidNeedException(
            "invalid_template",
            f"{name} option must be a string or None, got {converted}.",
        )


def _convert_to_str_func(
    name: str, converted: FieldLiteralValue | FieldFunctionArray | None
) -> tuple[str, None | FieldFunctionArray]:
    if isinstance(converted, FieldLiteralValue) and isinstance(converted.value, str):
        return converted.value, None
    elif isinstance(converted, FieldFunctionArray) and all(
        isinstance(x, str | DynamicFunctionParsed | VariantFunctionParsed)
        for x in converted
    ):
        return "", converted
    else:
        raise InvalidNeedException(
            "invalid_value",
            f"{name} must be a string or function, got {converted}.",
        )


def _convert_to_none_str_func(
    name: str, converted: FieldLiteralValue | FieldFunctionArray | None
) -> tuple[None | str, None | FieldFunctionArray]:
    if converted is None:
        return None, None
    elif isinstance(converted, FieldLiteralValue) and isinstance(converted.value, str):
        return converted.value, None
    elif isinstance(converted, FieldFunctionArray) and all(
        isinstance(x, str | DynamicFunctionParsed | VariantFunctionParsed)
        for x in converted
    ):
        return None, converted
    else:
        raise InvalidNeedException(
            "invalid_value",
            f"{name} must be none, string or function, got {converted}.",
        )


def _convert_to_bool_func(
    name: str, converted: FieldLiteralValue | FieldFunctionArray | None
) -> tuple[bool, FieldFunctionArray | None]:
    if isinstance(converted, FieldLiteralValue) and isinstance(converted.value, bool):
        return converted.value, None
    elif (
        isinstance(converted, FieldFunctionArray)
        and len(converted.value) == 1
        and isinstance(
            converted.value[0], bool | DynamicFunctionParsed | VariantFunctionParsed
        )
    ):
        return False, converted
    else:
        raise InvalidNeedException(
            "invalid_value",
            f"{name} must be a boolean or function, got {converted}.",
        )


def _convert_to_list_str_func(
    name: str, converted: FieldLiteralValue | FieldFunctionArray | None
) -> tuple[list[str], None | FieldFunctionArray]:
    if (
        isinstance(converted, FieldLiteralValue)
        and isinstance(converted.value, list)
        and all(isinstance(t, str) for t in converted.value)
    ):
        return cast(list[str], converted.value), None
    elif isinstance(converted, FieldFunctionArray) and all(
        isinstance(x, str | DynamicFunctionParsed | VariantFunctionParsed)
        for x in converted
    ):
        return [], converted
    else:
        raise InvalidNeedException(
            "invalid_value",
            f"{name} must be a comma separated string, list of strings or function, got {converted}.",
        )


def add_need(
    app: Sphinx,
    state: None | RSTState = None,
    docname: None | str = None,
    lineno: None | int = None,
    need_type: str = "",
    title: str = "",
    *,
    need_source: NeedItemSourceProtocol | None = None,
    id: str | None = None,
    content: str | StringList = "",
    lineno_content: None | int = None,
    doctype: None | str = None,
    status: str | None = None,
    tags: None | str | list[str] = None,
    constraints: None | str | list[str] = None,
    parts: dict[str, NeedsPartType] | None = None,
    arch: dict[str, str] | None = None,
    signature: None | str = None,
    sections: list[str] | None = None,
    jinja_content: bool | None = None,
    hide: None | bool | str = None,
    collapse: None | bool | str = None,
    style: None | str = None,
    layout: None | str = None,
    template: None | str = None,
    pre_template: str | None = None,
    post_template: str | None = None,
    is_import: bool = False,
    is_external: bool = False,
    external_url: str | None = None,
    external_css: str = "external_link",
    full_title: str | None = None,
    **kwargs: Any,
) -> list[nodes.Node]:
    """
    Creates a new need and returns its node.

    ``add_need`` allows to create needs programmatically and use its returned node to be integrated in any
    docutils based structure.

    ``kwargs`` can contain options defined in ``needs_extra_options`` and ``needs_extra_links``.
    If an entry is found in ``kwargs``, which *is not* specified in the configuration or registered e.g. via
    ``add_extra_option``, an exception is raised.

    If ``is_external`` is set to ``True``, no node will be created.
    Instead, the need is referencing an external url.
    Used mostly for :ref:`needs_external_needs` to integrate and reference needs from external documentation.

    :raises InvalidNeedException: If the need could not be added due to a validation issue.

    If the need is within the current project, i.e. not an external need,
    the following parameters are used to help provide source mapped warnings and errors:

    :param docname: documentation identifier, for the referencing document.
    :param lineno: line number of the top of the directive (1-indexed).
    :param lineno_content: line number of the content start of the directive (1-indexed).

    Otherwise, the following parameters are used:

    :param is_external: Is true, no node is created and need is referencing external url
    :param external_url: URL as string, which is used as target if ``is_external`` is ``True``
    :param external_css: CSS class name as string, which is set for the <a> tag.

    Additional parameters:

    :param app: Sphinx application object.
    :param state: Current state object.
    :param need_type: Name of the need type to create.
    :param title: String as title.
    :param full_title: This is given, if an auto-generated title was trimmed.
        It is used to auto-generate the ID, if required.
    :param id: ID as string. If not given, an id will get generated.
    :param content: Content of the need, either as a ``str``
        or a ``StringList`` (a string with mapping to the source text).
    :param status: Status as string.
    :param tags: A list of tags, or a comma separated string.
    :param constraints: Constraints as single, comma separated, string.
    :param constraints_passed: Contains bool describing if all constraints have passed
    :param hide: If True then the need is not rendered.
        ``None`` means that the value can be overriden by global defaults, else it is set to False.
    :param collapse: If True, then hide the meta-data information of the need.
        ``None`` means that the value can be overriden by global defaults, else it is set to False.
    :param style: String value of class attribute of node.
    :param layout: String value of layout definition to use
    :param template: Template name to use for the content of this need
    :param pre_template: Template name to use for content added before need
    :param post_template: Template name to use for the content added after need

    :return: list of nodes
    """
    # remove deprecated kwargs
    if kwargs.keys() & _deprecated_kwargs:
        warnings.warn(
            "deprecated key found in kwargs", DeprecationWarning, stacklevel=1
        )
        kwargs = {k: v for k, v in kwargs.items() if k not in _deprecated_kwargs}

    if (
        doctype is None
        and not (need_source.dict_repr["is_external"] if need_source else is_external)
        and (_docname := need_source.dict_repr["docname"] if need_source else docname)
    ):
        doctype = os.path.splitext(app.env.doc2path(_docname))[1]

    needs_info = generate_need(
        needs_config=NeedsSphinxConfig(app.config),
        needs_schema=SphinxNeedsData(app.env).get_schema(),
        need_source=need_source,
        need_type=need_type,
        title=title,
        full_title=full_title,
        docname=docname,
        lineno=lineno,
        id=id,
        doctype=doctype or "",
        content="\n".join(content) if isinstance(content, StringList) else content,
        lineno_content=lineno_content,
        status=status,
        tags=tags,
        constraints=constraints,
        parts=parts,
        arch=arch,
        signature=signature,
        sections=sections,
        jinja_content=jinja_content,
        hide=hide,
        collapse=collapse,
        style=style,
        layout=layout,
        template_root=Path(str(app.srcdir)),
        template=template,
        pre_template=pre_template,
        post_template=post_template,
        is_import=is_import,
        is_external=is_external,
        external_url=external_url,
        external_css=external_css,
        **kwargs,
    )

    if SphinxNeedsData(app.env).has_need(needs_info["id"]):
        if id is None:
            # this is a generated ID
            message = f"Unique ID could not be generated for need with title {needs_info['title']!r}."
        else:
            message = f"A need with ID {needs_info['id']!r} already exists."
        raise InvalidNeedException("duplicate_id", message)

    SphinxNeedsData(app.env).add_need(needs_info)

    if needs_info["is_external"]:
        return []

    assert state is not None, "parser state must be set if need is not external"

    if needs_info["jinja_content"] or needs_info["template"]:
        # if the content was generated by jinja,
        # then we can no longer use the original potentially source mapped StringList
        content = needs_info["content"]

    return _create_need_node(needs_info, app.env, state, content)


@contextmanager
def _reset_rst_titles(state: RSTState) -> Iterator[None]:
    """Temporarily reset the title styles and section level in the parser state,
    so that title styles can have different levels to the surrounding document.
    """
    # this is basically a horrible hack to get the docutils parser to work correctly with generated content
    surrounding_title_styles = state.memo.title_styles
    surrounding_section_level = state.memo.section_level
    state.memo.title_styles = []
    state.memo.section_level = 0
    yield
    state.memo.title_styles = surrounding_title_styles
    state.memo.section_level = surrounding_section_level


def _create_need_node(
    data: NeedItem,
    env: BuildEnvironment,
    state: RSTState,
    content: str | StringList,
) -> list[nodes.Node]:
    """Create a Need node (and surrounding nodes) to be added to the document.

    Note, some additional data is added to the node once the whole document has been processed
    (see ``process_need_nodes()``).

    :param data: The full data entry for this node.
    :param env: The Sphinx environment.
    :param state: The current parser state.
    :param content: The main content to be rendered inside the need.
        Note, this content my be different to ``data["content"]``,
        in that it may be a ``StringList`` type with source-mapping directly parsed from a directive.
    """
    source = env.doc2path(data["docname"]) if data["docname"] else None

    style_classes = ["need", f"need-{data['type'].lower()}"]
    if data["style"]:
        style_classes.append(data["style"])

    node_need = Need("", classes=style_classes, ids=[data["id"]], refid=data["id"])
    node_need.source, node_need.line = source, data["lineno"]

    if data["hide"]:
        # still add node to doctree, so we can later compute its relative location in the document
        # (see analyse_need_locations function)
        # TODO this is problematic because it will not populate ``parts`` or ``arch`` of the need,
        # nor will it find/add any child needs
        node_need["hidden"] = True
        return [node_need]

    return_nodes: list[nodes.Node] = []

    if pre_content := data.get("pre_content"):
        node = nodes.Element()
        with _reset_rst_titles(state):
            state.nested_parse(
                StringList(pre_content.splitlines(), source=source),
                (data["lineno"] - 1) if data["lineno"] else 0,
                node,
                match_titles=True,
            )
        return_nodes.extend(node.children)

    # Calculate target id, to be able to set a link back
    return_nodes.append(
        nodes.target("", "", ids=[data["id"]], refid=data["id"], anonymous="")
    )

    content_offset = 0
    if data["lineno_content"]:
        content_offset = data["lineno_content"] - 1
    elif data["lineno"]:
        content_offset = data["lineno"] - 1
    if isinstance(content, StringList):
        state.nested_parse(content, content_offset, node_need, match_titles=False)
    else:
        state.nested_parse(
            StringList(content.splitlines(), source=source),
            content_offset,
            node_need,
            match_titles=False,
        )

    # Extract plantuml diagrams and store needumls with keys in arch, e.g. need_info['arch']['diagram']
    arch = {}
    node_need_needumls_without_key = []
    node_need_needumls_key_names = []
    for child in node_need.children:
        if isinstance(child, Needuml):
            needuml_id = child.rawsource
            if needuml := SphinxNeedsData(env).get_or_create_umls().get(needuml_id):
                try:
                    key_name = needuml["key"]
                    if key_name:
                        # check if key_name already exists in needs_info["arch"]
                        if key_name in node_need_needumls_key_names:
                            raise NeedumlException(
                                f"Inside need: {data['id']}, found duplicate Needuml option key name: {key_name}"
                            )
                        else:
                            arch[key_name] = needuml["content"]
                            node_need_needumls_key_names.append(key_name)
                    else:
                        node_need_needumls_without_key.append(needuml)
                except KeyError:
                    pass

    # only store the first needuml-node which has no key option under diagram
    if node_need_needumls_without_key:
        arch["diagram"] = node_need_needumls_without_key[0]["content"]

    data["arch"] = arch

    need_parts = find_parts(node_need)
    update_need_with_parts(env, data, need_parts)

    SphinxNeedsData(env).set_need_node(data["id"], node_need)

    return_nodes.append(node_need)

    if post_content := data.get("post_content"):
        node = nodes.Element()
        with _reset_rst_titles(state):
            state.nested_parse(
                StringList(post_content.splitlines(), source=source),
                (data["lineno"] - 1) if data["lineno"] else 0,
                node,
                match_titles=True,
            )
        return_nodes.extend(node.children)

    return return_nodes


def del_need(app: Sphinx, need_id: str) -> None:
    """
    Deletes an existing need.

    :param app: Sphinx application object.
    :param need_id: Sphinx need id.
    """
    data = SphinxNeedsData(app.env)
    if not data.has_need(need_id):
        log_warning(logger, f"Given need id {need_id} not exists!", "delete_need", None)
    else:
        data.remove_need(need_id)


def add_external_need(
    app: Sphinx,
    need_type: str,
    title: str | None = None,
    id: str | None = None,
    need_source: NeedItemSourceProtocol | None = None,
    external_url: str | None = None,
    external_css: str = "external_link",
    content: str = "",
    status: str | None = None,
    tags: str | list[str] | None = None,
    constraints: str | None = None,
    **kwargs: Any,
) -> list[nodes.Node]:
    """
    Adds an external need from an external source.
    This need does not have any representation in the current documentation project.
    However, it can be linked and filtered.
    It's reference will open a link to another, external  sphinx documentation project.

    It returns an empty list (without any nodes), so no nodes will be added to the document.

    :param app: Sphinx application object.
    :param need_type: Name of the need type to create.
    :param title: String as title.
    :param id: ID as string. If not given, a id will get generated.
    :param external_url: URL as string, which shall be used as link to the original need source
    :param content: Content as single string.
    :param status: Status as string.
    :param tags: A list of tags, or a comma separated string.
    :param constraints: constraints as single, comma separated string.
    :param external_css: CSS class name as string, which is set for the <a> tag.

    :raises InvalidNeedException: If the need could not be added due to a validation issue.

    """
    for fixed_key in ("state", "docname", "lineno", "is_external"):
        if fixed_key in kwargs:
            kwargs.pop(fixed_key)
            # TODO Although it seems prudent to not silently ignore user input here,
            # raising an error here currently breaks some existing tests
            # raise ValueError(
            #     f"{fixed_key} is not allowed in kwargs for add_external_need"
            # )

    return add_need(
        app=app,
        need_source=need_source,
        need_type=need_type,
        id=id,
        content=content,
        # TODO a title being None is not "type compatible" with other parts of the code base,
        # however, at present changing it to an empty string breaks some existing tests.
        title=title,  # type: ignore
        status=status,
        tags=tags,
        constraints=constraints,
        is_external=True,
        external_url=external_url,
        external_css=external_css,
        **kwargs,
    )


def _prepare_template(
    needs_config: NeedsSphinxConfig,
    needs_info: NeedItem,
    template_name: str,
    template_root: None | Path,
) -> str:
    template_folder = Path(needs_config.template_folder)
    if not template_folder.is_absolute():
        if template_root is None:
            raise InvalidNeedException(
                "invalid_template",
                "Template folder is not an absolute path and no template_root is given.",
            )
        template_folder = template_root / template_folder

    if not template_folder.is_dir():
        raise InvalidNeedException(
            "invalid_template", f"Template folder does not exist: {template_folder}"
        )

    template_file_name = f"{template_name}.need"
    template_path = template_folder / template_file_name
    if not template_path.is_file():
        raise InvalidNeedException(
            "invalid_template", f"Template does not exist: {template_path}"
        )

    with template_path.open() as template_file:
        template_content = "".join(template_file.readlines())
    try:
        template_obj = Template(template_content)
        new_content = template_obj.render(**needs_info, **needs_config.render_context)
    except Exception as e:
        raise InvalidNeedException(
            "invalid_template",
            f"Error while rendering template {template_path}: {e}",
        )

    return new_content


def _make_hashed_id(
    type_prefix: str, full_title: str, content: str, config: NeedsSphinxConfig
) -> str:
    """Create an ID based on the type and title of the need."""
    hashable_content = full_title or content
    hashed = hashlib.sha1(hashable_content.encode("UTF-8")).hexdigest().upper()
    if config.id_from_title:
        hashed = full_title.upper().replace(" ", "_") + "_" + hashed
    return f"{type_prefix}{hashed[: config.id_length]}"


def _copy_links(
    links: dict[str, LinksLiteralValue | LinksFunctionArray | None],
    config: NeedsSphinxConfig,
) -> None:
    """Implement 'copy' logic for links."""
    if "links" not in links:
        return  # should not happen, but be defensive
    copy_links: list[str | DynamicFunctionParsed | VariantFunctionParsed] = []
    for link_type in config.extra_links:
        if link_type.get("copy", False) and (name := link_type["option"]) != "links":
            other = links[name]
            if isinstance(other, LinksLiteralValue | LinksFunctionArray):
                copy_links.extend(other.value)
    if any(
        isinstance(li, DynamicFunctionParsed | VariantFunctionParsed)
        for li in copy_links
    ):
        if links["links"] is None:
            links["links"] = LinksFunctionArray(tuple(copy_links))
        else:
            links["links"] = LinksFunctionArray(
                tuple(links["links"].value) + tuple(copy_links)
            )
    else:
        copy_links_literal = cast(list[str], copy_links)
        if links["links"] is None:
            links["links"] = LinksLiteralValue(copy_links_literal)
        elif isinstance(links["links"], LinksLiteralValue):
            links["links"].value.extend(copy_links_literal)
        else:
            links["links"] = LinksFunctionArray(
                tuple(links["links"].value) + tuple(copy_links_literal)
            )


class DefaultContextData(TypedDict):
    config: NeedsSphinxConfig
    core: PredicateContextData
    extras: dict[str, AllowedTypes | None]
    links: dict[str, list[str]]


def _get_field_default(
    scheme: FieldSchema | None,
    config: NeedsSphinxConfig,
    core: PredicateContextData,
    extras: dict[str, AllowedTypes | None],
    links: dict[str, list[str]],
) -> None | FieldLiteralValue | FieldFunctionArray:
    if scheme is None:
        return None  # TODO except (and catch upstream)
    # TODO if we stored default lists as tuples we could avoid the deepcopy here
    for predicate, v in scheme.predicate_defaults:
        if apply_default_predicate(predicate, config, core, extras, links):
            return deepcopy(v)
    if scheme.default is not None:
        return deepcopy(scheme.default)
    return None


def _get_links_default(
    scheme: LinkSchema | None,
    config: NeedsSphinxConfig,
    core: PredicateContextData,
    extras: dict[str, AllowedTypes | None],
    links: dict[str, list[str]],
) -> None | LinksLiteralValue | LinksFunctionArray:
    if scheme is None:
        return None  # TODO except (and catch upstream)
    # TODO if we stored default lists as tuples we could avoid the deepcopy here
    for predicate, v in scheme.predicate_defaults:
        if apply_default_predicate(predicate, config, core, extras, links):
            return deepcopy(v)
    if scheme.default is not None:
        return deepcopy(scheme.default)
    return None


def get_needs_view(app: Sphinx) -> NeedsView:
    """Return a read-only view of all resolved needs.

    .. important:: this should only be called within the write phase,
        after the needs have been fully collected.
        If not already done, this will ensure all needs are resolved
        (e.g. back links have been computed etc),
        and then lock the data to prevent further modification.
    """
    return SphinxNeedsData(app.env).get_needs_view()
