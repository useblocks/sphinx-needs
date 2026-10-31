from __future__ import annotations

import hashlib
import os
import re
import warnings
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal, TypedDict, TypeVar

from docutils import nodes
from docutils.parsers import Parser
from docutils.parsers.rst.states import RSTState
from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs._jinja import render_template_string
from sphinx_needs._need_source import (
    NeedSourceHop,
    NeedSourcePhysical,
    with_page_paths,
)
from sphinx_needs.config import NeedsSphinxConfig, NeedType
from sphinx_needs.data import (
    NeedsCoreFields,
    NeedsInfoType,
    NeedsPartType,
    SphinxNeedsData,
)
from sphinx_needs.derive import typed_empty
from sphinx_needs.directives.needuml import Needuml, NeedumlException
from sphinx_needs.exceptions import InvalidNeedException, NeedsInvalidFilter
from sphinx_needs.filter_common import (
    PredicateContextData,
    apply_default_predicate,
)
from sphinx_needs.functions.functions import DynamicFunctionParsed
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_content import (
    MarkupContent,
    parse_need_content,
    resolve_content_parser,
)
from sphinx_needs.need_item import (
    NeedItem,
    NeedItemSource,
    NeedItemSourceProtocol,
    NeedLink,
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
    TypeFieldsSchema,
)
from sphinx_needs.nodes import Need
from sphinx_needs.roles.need_part import find_parts, update_need_with_parts
from sphinx_needs.services.config.github import GITHUB_FIELDS
from sphinx_needs.utils import jinja_parse
from sphinx_needs.variant_data import VariantDataParsed
from sphinx_needs.variants import VariantFunctionParsed
from sphinx_needs.views import NeedsView
from ub_needs_exchange import map_legacy_keys

logger = get_logger(__name__)

_deprecated_kwargs = {
    "constraints_passed",
    "links_string",
    "hide_tags",
    "hide_status",
    "delete",
}


def _id_matched_by_patterns(need_id: str, /) -> str:
    """The id :ref:`needs_id_regex` and a need type's ``id_regex`` are matched against:
    the need's local id, as it is written in the need or generated, before any
    namespace. While a need's id carries no namespace, that is the whole id.

    The one place both patterns read the id from, so that they keep matching the local
    id should an id ever carry more.

    :param need_id: The id of the need being created.
    """
    return need_id


def generate_need(
    needs_config: NeedsSphinxConfig,
    needs_schema: FieldsSchema,
    need_type: str,
    title: str,
    *,
    need_source: NeedItemSourceProtocol | None = None,
    docname: str | None = None,
    lineno: int | None = None,
    id: str | None = None,
    doctype: str = ".rst",
    content: str = "",
    lineno_content: int | None = None,
    status: str | None = None,
    tags: str | list[str] | None = None,
    constraints: str | list[str] | None = None,
    parts: dict[str, NeedsPartType] | None = None,
    arch: dict[str, str] | None = None,
    signature: str | None = None,
    sections: Sequence[str] | None = None,
    jinja_content: bool | None = None,
    hide: bool | str | None = None,
    collapse: bool | str | None = None,
    style: str | None = None,
    layout: str | None = None,
    template_root: Path | None = None,
    template: str | None = None,
    pre_template: str | None = None,
    post_template: str | None = None,
    is_import: bool = False,
    is_external: bool = False,
    external_url: str | None = None,
    external_css: str = "external_link",
    full_title: str | None = None,
    allow_type_coercion: bool = True,
    **kwargs: Any,
) -> NeedItem:
    """Creates a validated need data entry, without adding it to the project.

    .. important:: This function does not parse or analyse the content,
        and so will not auto-populate the ``parts`` or ``arch`` fields of the need
        from the content.

        It will also not validate that the ID is not already in use within the project.

    :raises InvalidNeedException: If the data fails any validation issue.

    ``kwargs`` can contain options defined in ``needs_fields`` and ``needs_links``.
    If an entry is found in ``kwargs``, which *is not* specified in the configuration or registered e.g. via
    ``add_field``, an exception is raised.

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
    :param constraints: Constraint names as comma separated string or list of strings
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
    :param allow_type_coercion: If true, values will be coerced to the expected type where possible.
    """
    return _generate_need(
        needs_config,
        needs_schema,
        need_type,
        title,
        source=_legacy_source(
            need_source,
            docname=docname,
            lineno=lineno,
            lineno_content=lineno_content,
            is_import=is_import,
            is_external=is_external,
            external_url=external_url,
        ),
        values={
            "status": status,
            "tags": tags,
            "constraints": constraints,
            "hide": hide,
            "collapse": collapse,
            "style": style,
            "layout": layout,
            "template": template,
            "pre_template": pre_template,
            "post_template": post_template,
            **kwargs,
        },
        id=id,
        doctype=doctype,
        content=content,
        parts=parts,
        arch=arch,
        signature=signature,
        sections=sections,
        jinja_content=jinja_content,
        template_root=template_root,
        external_css=external_css,
        full_title=full_title,
        allow_type_coercion=allow_type_coercion,
    )


def _legacy_source(
    need_source: NeedItemSourceProtocol | None,
    *,
    docname: str | None = None,
    lineno: int | None = None,
    lineno_content: int | None = None,
    is_import: bool = False,
    is_external: bool = False,
    external_url: str | None = None,
) -> NeedItemSourceProtocol:
    """The source :func:`add_need`, :func:`generate_need` and :func:`add_external_need`
    record: the one given, else the API's default, made from their location keywords --
    the page of ``docname``, and an external need's ``external`` hop (its URL, where it
    has one) before it."""
    if need_source is not None:
        return need_source
    hops = NeedItemSource.on_page(docname).hops
    if is_external:
        hops = (
            NeedSourceHop(
                kind="external",
                physical=None
                if external_url is None
                else NeedSourcePhysical(url=external_url),
            ),
            *hops,
        )
    return NeedItemSource(
        hops, lineno=lineno, lineno_content=lineno_content, is_import=is_import
    )


def _generate_need(
    needs_config: NeedsSphinxConfig,
    needs_schema: FieldsSchema,
    need_type: str,
    title: str,
    *,
    source: NeedItemSourceProtocol,
    values: Mapping[str, Any],
    id: str | None = None,
    doctype: str = ".rst",
    content: str = "",
    parts: dict[str, NeedsPartType] | None = None,
    arch: dict[str, str] | None = None,
    signature: str | None = None,
    sections: Sequence[str] | None = None,
    jinja_content: bool | None = None,
    template_root: Path | None = None,
    external_css: str | None = "external_link",
    full_title: str | None = None,
    allow_type_coercion: bool = True,
) -> NeedItem:
    """The body of :func:`generate_need`, which every creation path shares.

    :param values: The need's field and link values, by name: the core fields of the
        field schema (``title`` excepted, which is an argument of its own), the extra
        fields and the link types. A value ``None`` is a value not given. Never
        keyword arguments, so that no field name meets a parameter (#2392).
    :raises InvalidNeedException: If the data fails any validation issue; (type
        ``invalid_kwargs``) if ``values`` names no field or link type of the need's
        type.
    """
    # location is used to provide source mapped warnings
    location = (
        (source.dict_repr["docname"], source.dict_repr["lineno"])
        if source.dict_repr["docname"]
        else None
    )

    # the fields of a need of this type, as the type declares them
    schema = needs_schema.for_type(need_type)

    #: the core fields of the field schema, which ``values`` sets (``title`` excepted)
    core_names = [name for name in schema.iter_core_field_names() if name != "title"]
    # validate the values
    allowed_kwargs = {
        *core_names,
        *schema.iter_link_field_names(),
        *schema.iter_extra_field_names(),
    }
    unknown_kwargs = set(values) - allowed_kwargs
    if unknown_kwargs:
        raise InvalidNeedException(
            "invalid_kwargs",
            f"{unknown_kwargs!r} not in 'needs_fields' or 'needs_links'.",
        )

    # get the need type data
    need_type_data = _get_need_type(needs_config, need_type)

    # generate and validate the id
    if id is None and needs_config.id_required:
        raise InvalidNeedException(
            "missing_id", "No ID defined, but 'needs_id_required' is set to True."
        )
    need_id = (
        _generate_need_id(
            needs_config, need_type_data["prefix"], title, content, full_title
        )
        if id is None
        else id
    )
    # a need from outside the project's sources (imported, external) is the source's
    # data: its id is not checked against ``needs_id_regex`` (a prefix may break any
    # pattern), and it keeps the values of its derived fields
    from_outside = bool(
        source.dict_repr["is_import"] or source.dict_repr["is_external"]
    )
    #: what the patterns test: the need's local id
    matched_id = _id_matched_by_patterns(need_id)
    if (
        needs_config.id_regex
        and not from_outside
        and not re.match(needs_config.id_regex, matched_id)
    ):
        raise InvalidNeedException(
            "invalid_id",
            f"Given ID {need_id!r} does not match configured regex {needs_config.id_regex!r}",
        )
    # and the id_regex of its need type, and of each type that one inherits from
    for declared_by, pattern in (
        () if from_outside else needs_schema.id_patterns(need_type)
    ):
        if not re.match(pattern, matched_id):
            inherited = (
                ""
                if declared_by == need_type
                else f", which need type {need_type!r} inherits"
            )
            raise InvalidNeedException(
                "invalid_id",
                f"Given ID {need_id!r} does not match the id_regex {pattern!r} of need "
                f"type {declared_by!r}{inherited}",
            )

    # Convert all schema-enabled core fields
    _raw_core: dict[str, Any] = {
        "title": title,
        **{name: values.get(name) for name in core_names},
    }
    core_converted: dict[str, FieldLiteralValue | FieldFunctionArray | None] = {}
    for _name, _raw in _raw_core.items():
        _fs = schema.get_core_field(_name)
        assert _fs is not None, f"{_name} field schema does not exist"
        try:
            core_converted[_name] = (
                None
                if _raw is None
                else _fs.convert_or_type_check(_raw, allow_coercion=allow_type_coercion)
            )
        except Exception as err:
            raise InvalidNeedException(
                "invalid_value", f"{_name!r} value is invalid: {err}"
            ) from err

    if (
        isinstance(core_converted["constraints"], FieldLiteralValue)
        and isinstance(core_converted["constraints"].value, Iterable)
        and (
            unknown_constraints := set(core_converted["constraints"].value)
            - set(needs_config.constraints)
        )
    ):
        # TODO this check should be later in processing, once we have resolved any dynamic functions
        raise InvalidNeedException(
            "invalid_constraints",
            f"Constraints {unknown_constraints!r} not in 'needs_constraints'.",
        )

    # a need from outside keeps the values of its derived fields, as data; any other
    # need takes the rule's value, and what an author wrote in a derived field is
    # ignored. A field declared on need types alone is absent on the needs of every
    # other type, from outside or not: a value given for it is ignored, and reported
    # unless it is what the need holds anyway (a needs.json carries every field, the
    # empty ones too)
    extras_no_defaults: dict[str, FieldLiteralValue | FieldFunctionArray | None] = {}
    #: the fields an author cannot set: their value is final, no default applies
    final: set[str] = set()
    for extra_field in schema.iter_extra_fields():
        # a derived field the type does not declare is absent: no data from outside
        authored = not extra_field.derived or not schema.declares(extra_field.name)
        if not extra_field.directive_option and (
            authored or not from_outside or values.get(extra_field.name) is None
        ):
            if not from_outside or (
                authored
                and values.get(extra_field.name) != extra_field.off_type_value()
            ):
                _refuse_authored(
                    extra_field,
                    values,
                    location,
                    need_type,
                    need_id,
                    declared=schema.declares(extra_field.name),
                )
            extras_no_defaults[extra_field.name] = _unauthored_value(
                extra_field, need_type
            )
            final.add(extra_field.name)
        elif extra_field.name not in values:
            extras_no_defaults[extra_field.name] = None
        else:
            try:
                extras_no_defaults[extra_field.name] = (
                    None
                    if values[extra_field.name] is None
                    else extra_field.convert_or_type_check(
                        values[extra_field.name], allow_coercion=allow_type_coercion
                    )
                )
            except Exception as err:
                raise InvalidNeedException(
                    "invalid_field_value",
                    f"Field {extra_field.name!r} is invalid: {err}",
                ) from err

    links_no_defaults: dict[str, LinksLiteralValue | LinksFunctionArray | None] = {}
    for link_field in schema.iter_link_fields():
        # a derived link type the type does not declare is absent: no data from outside
        authored = not link_field.derived or not schema.declares(link_field.name)
        if not link_field.directive_option and (
            authored or not from_outside or values.get(link_field.name) is None
        ):
            if not from_outside or (
                authored and values.get(link_field.name) != link_field.off_type_value()
            ):
                _refuse_authored(
                    link_field,
                    values,
                    location,
                    need_type,
                    need_id,
                    declared=schema.declares(link_field.name),
                )
            links_no_defaults[link_field.name] = LinksLiteralValue(
                link_field.off_type_value()
                if link_field.derived and link_field.rule_for(need_type) is None
                else []
            )
        elif link_field.name not in values:
            links_no_defaults[link_field.name] = None
        else:
            try:
                links_no_defaults[link_field.name] = (
                    None
                    if values[link_field.name] is None
                    else link_field.convert_or_type_check(
                        values[link_field.name], allow_coercion=allow_type_coercion
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
        "title": core_converted["title"].value
        if isinstance(core_converted["title"], FieldLiteralValue)
        else "",  # ty: ignore[invalid-argument-type]
        "tags": copy(core_converted["tags"].value)
        if isinstance(core_converted["tags"], FieldLiteralValue)
        else [],  # TODO allow for non-df/vf values?  # ty: ignore[invalid-argument-type]
        "status": core_converted["status"].value
        if isinstance(core_converted["status"], FieldLiteralValue)
        else None,  # ty: ignore[invalid-argument-type]
        "docname": source.dict_repr["docname"],
        "is_import": source.dict_repr["is_import"],
        "is_external": source.dict_repr["is_external"],
    }
    defaults_extras_ctx = {
        k: copy(v.value) if isinstance(v, FieldLiteralValue) else None
        for k, v in extras_no_defaults.items()
    }
    defaults_links_ctx = {
        k: [nl.to_filter_string() for nl in v.value]
        if isinstance(v, LinksLiteralValue)
        else []
        for k, v in links_no_defaults.items()
    }

    context: DefaultContextData = {
        "config": needs_config,
        "core": defaults_ctx,
        "extras": defaults_extras_ctx,
        "links": defaults_links_ctx,
        "location": location,
    }

    # Apply defaults to core fields (title excluded - always required)
    for _name in _raw_core:
        if _name == "title":
            continue
        if core_converted[_name] is None:
            core_converted[_name] = _get_field_default(
                schema.get_core_field(_name), **context
            )

    extras = {
        k: _get_field_default(schema.get_extra_field(k), **context)
        if v is None and k not in final
        else v
        for k, v in extras_no_defaults.items()
    }
    links = {
        k: _get_links_default(schema.get_link_field(k), **context) if v is None else v
        for k, v in links_no_defaults.items()
    }
    _copy_links(links, schema)

    # Unwrap core fields: extract concrete values and dynamic functions
    dynamic_fields: dict[str, FieldFunctionArray | LinksFunctionArray] = {}
    core_values: dict[str, Any] = {}
    for _name in _raw_core:
        _fs = schema.get_core_field(_name)
        assert _fs is not None
        core_values[_name], _func = _unwrap_field_value(_fs, core_converted[_name])
        if _func is not None:
            dynamic_fields[_name] = _func

    # Add the need and all needed information
    core_data: NeedsInfoType = {
        "id": need_id,
        "type": need_type,
        "type_name": need_type_data["title"],
        "type_prefix": need_type_data["prefix"],
        "type_color": need_type_data.get("color") or "",
        "type_style": need_type_data.get("style") or "node",
        "title": core_values["title"],
        "status": core_values["status"],
        "tags": core_values["tags"],
        "constraints": core_values["constraints"],
        "collapse": core_values["collapse"],
        "hide": core_values["hide"],
        "style": core_values["style"],
        "layout": core_values["layout"],
        "external_css": external_css or "external_link",
        "arch": arch or {},
        "has_dead_links": False,
        "has_forbidden_dead_links": False,
        "sections": tuple(sections or ()),
        "signature": signature,
    }

    content_info = NeedsContent(
        doctype=doctype,
        content=content,
        pre_content=None,
        post_content=None,
        template=core_values["template"],
        pre_template=core_values["pre_template"],
        post_template=core_values["post_template"],
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
        extra_schema = schema.get_extra_field(k)
        if extra_schema is None:
            raise InvalidNeedException(
                "invalid_field_value",
                f"Field {k!r} not in 'needs_fields'.",
            )
        extras_pre[k], _func = _unwrap_field_value(extra_schema, v)
        if _func is not None:
            dynamic_fields[k] = _func

    links_pre: dict[str, list[NeedLink]] = {}
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
            # one set for every need type, the schema's own (derived_names)
            derived=schema.derived_names,
            _validate=False,
        )
    except ValueError as err:
        raise InvalidNeedException("failed_init", str(err)) from err

    _template = core_values["template"]
    _pre_template = core_values["pre_template"]
    _post_template = core_values["post_template"]
    if jinja_content or _template or _pre_template or _post_template:
        # TODO ideally perform all these content alterations before creating the need item
        if jinja_content:
            need_content_context: dict[str, Any] = needs_info.filter_context()
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

        if _template:
            # TODO should warn if content is not empty?
            content_info = replace(
                content_info,
                content=_prepare_template(
                    needs_config, needs_info, _template, template_root
                ),
            )

        if _pre_template:
            content_info = replace(
                content_info,
                pre_content=_prepare_template(
                    needs_config, needs_info, _pre_template, template_root
                ),
            )

        if _post_template:
            content_info = replace(
                content_info,
                post_content=_prepare_template(
                    needs_config, needs_info, _post_template, template_root
                ),
            )

        needs_info.set_content(content_info)

    return needs_info


def _refuse_authored(
    field_schema: FieldSchema | LinkSchema,
    kwargs: Mapping[str, Any],
    location: tuple[str | None, int | None] | None,
    need_type: str,
    need_id: str,
    *,
    declared: bool = True,
) -> None:
    """Report a value given for a field an author cannot set: a derived one, or one
    declared on need types alone that the need's type does not declare (``declared``
    false; derived or not, as it is absent on the type).

    The value, a literal or a ``[[…]]``, ``<<…>>`` or ``<{…}>``, is ignored; also on a
    need of a type a derived field has no rule for, which holds the field's default.
    """
    if (value := kwargs.get(field_schema.name)) is None:
        return
    what = "Link type" if isinstance(field_schema, LinkSchema) else "Field"
    if not declared or not field_schema.derived:
        # every global declaration an author cannot set is derived: this is the
        # declaration of a need type that does not declare the field
        log_warning(
            logger,
            f"{what} {field_schema.name!r} is not declared on need type {need_type!r} "
            f"and cannot be set in need {need_id!r}; the value {value!r} is ignored",
            "undeclared_for_type",
            location,
        )
        return
    if (type_rule := field_schema.rule_for(need_type)) is not None:
        rule = f"derived ({type_rule.describe()})"
    else:
        rule = f"derived (with no rule on need type {need_type!r})"
    log_warning(
        logger,
        f"{what} {field_schema.name!r} is {rule} and cannot be set in a need; "
        f"the value {value!r} is ignored",
        "derive_authored",
        location,
    )


def _unauthored_value(
    field_schema: FieldSchema, need_type: str
) -> FieldLiteralValue | None:
    """The value of a field an author cannot set, at the need's creation.

    A derived field holds its empty value until its rule computes it: ``None`` when it
    is nullable, else the empty value of its type. On a need of a type it has no rule
    for, it holds that type's value for good: its default (see
    :meth:`~sphinx_needs.needs_schema.FieldSchema.off_type_value`).
    """
    if field_schema.derived and field_schema.rule_for(need_type) is None:
        value = field_schema.off_type_value()
        return None if value is None else FieldLiteralValue(value)
    if field_schema.nullable:
        return None
    return FieldLiteralValue(_typed_empty(field_schema))


def _typed_empty(field_schema: FieldSchema) -> Any:
    """The empty value of a field's type: ``""``, ``False``, ``0``, ``0.0`` or ``[]``.

    :raises InvalidNeedException: If the field's type is unknown.
    """
    if (empty := typed_empty(field_schema.type)) is None:
        raise InvalidNeedException(
            "invalid_value",
            f"Field {field_schema.name!r} has unknown type {field_schema.type!r}.",
        )
    return empty


def _unwrap_field_value(
    field_schema: FieldSchema,
    converted: FieldLiteralValue | FieldFunctionArray | None,
) -> tuple[Any, FieldFunctionArray | None]:
    """Unwrap a converted field value into a concrete value and optional dynamic function.

    A field without a value holds ``None`` where its declaration admits it
    (:attr:`~sphinx_needs.needs_schema.FieldSchema.admits_null`): it is nullable, or
    not nullable at a ``severity`` below ``violation``, which the schema validation
    reports rather than the need being refused.

    :param field_schema: The schema for the field.
    :param converted: The converted value from ``convert_or_type_check``.
    :return: A tuple of (concrete_value, dynamic_func_or_none).
    :raises InvalidNeedException: If the value is invalid for the field.
    """
    if converted is None:
        if not field_schema.admits_null:
            raise InvalidNeedException(
                "invalid_value",
                f"Field {field_schema.name!r} is not nullable, but no value or default was given.",
            )
        return None, None
    elif isinstance(converted, FieldLiteralValue):
        return converted.value, None
    elif isinstance(converted, FieldFunctionArray):
        # Use a type-appropriate placeholder while the dynamic function is unresolved
        placeholder = None if field_schema.nullable else _typed_empty(field_schema)
        return placeholder, converted
    else:
        raise InvalidNeedException(
            "invalid_value",
            f"Field {field_schema.name!r} has unexpected value type {type(converted).__name__}.",
        )


def add_need(
    app: Sphinx,
    state: RSTState | None = None,
    docname: str | None = None,
    lineno: int | None = None,
    need_type: str = "",
    title: str = "",
    *,
    need_source: NeedItemSourceProtocol | None = None,
    id: str | None = None,
    content: str | StringList | MarkupContent = "",
    lineno_content: int | None = None,
    doctype: str | None = None,
    status: str | None = None,
    tags: str | list[str] | None = None,
    constraints: str | list[str] | None = None,
    parts: dict[str, NeedsPartType] | None = None,
    arch: dict[str, str] | None = None,
    signature: str | None = None,
    sections: list[str] | None = None,
    jinja_content: bool | None = None,
    hide: bool | str | None = None,
    collapse: bool | str | None = None,
    style: str | None = None,
    layout: str | None = None,
    template: str | None = None,
    pre_template: str | None = None,
    post_template: str | None = None,
    is_import: bool = False,
    is_external: bool = False,
    external_url: str | None = None,
    external_css: str = "external_link",
    full_title: str | None = None,
    allow_type_coercion: bool = True,
    **kwargs: Any,
) -> list[nodes.Node]:
    """
    Creates a new need and returns its node.

    ``add_need`` allows to create needs programmatically and use its returned node to be integrated in any
    docutils based structure.

    .. deprecated:: 9.2.0

       Use :func:`create_need`, which takes the need's location as a
       :class:`~sphinx_needs.need_item.NeedItemSource`
       (``NeedItemSource.from_directive(self)`` in a directive) and its fields and links
       as two mappings, and returns the need with its nodes. Each call is a
       ``DeprecationWarning`` at the calling line; ``add_need`` is removed in 10.0. See
       :ref:`api_migrating_add_need`.

    ``kwargs`` can contain options defined in ``needs_fields`` and ``needs_links``.
    If an entry is found in ``kwargs``, which *is not* specified in the configuration or registered e.g. via
    ``add_field``, an exception is raised.

    If ``is_external`` is set to ``True``, no node will be created.
    Instead, the need is referencing an external url.
    Used mostly for :ref:`needs_external_needs` to integrate and reference needs from external documentation.

    :raises InvalidNeedException: If the need could not be added due to a validation issue;
        also, before the need is recorded, if a ``MarkupContent``'s ``markup`` names no
        reStructuredText or MyST parser of the project.

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
        or a ``StringList`` (a string with mapping to the source text), parsed by the
        parser of the document the need is created in; or as a
        :class:`~sphinx_needs.api.MarkupContent`, the content with the markup it is
        written in (parsed by that markup's parser) and optionally the file and line it
        came from. See :ref:`api_content_markup`.

        .. versionchanged:: 9.0.0 ``content`` may be a ``MarkupContent``.

    :param doctype: The source suffix the need is recorded as written in
        (e.g. ``".rst"``). If not given, it is the ``markup`` of a ``MarkupContent``
        content, else the suffix of the document the need is created in.
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
    :param allow_type_coercion: If true, values will be coerced to the expected type where possible.

    :return: list of nodes
    """
    warnings.warn(
        "add_need is deprecated and will be removed in sphinx-needs 10.0: use "
        "sphinx_needs.api.create_need, which takes the need's location as a "
        "NeedItemSource (NeedItemSource.from_directive(self) in a directive) and its "
        "fields and links as two mappings; see 'Migrating from add_need' in the API "
        "documentation",
        DeprecationWarning,
        stacklevel=2,
    )
    # remove deprecated kwargs
    if kwargs.keys() & _deprecated_kwargs:
        warnings.warn(
            "deprecated key found in kwargs", DeprecationWarning, stacklevel=1
        )
        kwargs = {k: v for k, v in kwargs.items() if k not in _deprecated_kwargs}

    _, need_nodes = _create_need(
        app,
        state,
        _legacy_source(
            need_source,
            docname=docname,
            lineno=lineno,
            lineno_content=lineno_content,
            is_import=is_import,
            is_external=is_external,
            external_url=external_url,
        ),
        need_type,
        title,
        values={
            "status": status,
            "tags": tags,
            "constraints": constraints,
            "hide": hide,
            "collapse": collapse,
            "style": style,
            "layout": layout,
            "template": template,
            "pre_template": pre_template,
            "post_template": post_template,
            **kwargs,
        },
        id=id,
        content=content,
        doctype=doctype,
        jinja_content=jinja_content,
        full_title=full_title,
        allow_type_coercion=allow_type_coercion,
        parts=parts,
        arch=arch,
        signature=signature,
        sections=sections,
        external_css=external_css,
    )
    return need_nodes


def create_need(
    app: Sphinx,
    state: RSTState | None,
    source: NeedItemSourceProtocol,
    need_type: str,
    title: str,
    *,
    id: str | None = None,
    fields: Mapping[str, Any] | None = None,
    links: Mapping[str, Any] | None = None,
    content: str | StringList | MarkupContent = "",
    doctype: str | None = None,
    jinja_content: bool | None = None,
    full_title: str | None = None,
    allow_type_coercion: bool = True,
) -> tuple[NeedItem, list[nodes.Node]]:
    """Create a need, record it in the project, and return it with its nodes.

    The need's field values and its links are two mappings, kept apart from the
    function's own parameters, so any name the project declares for a field or a link
    type can be used: nothing a project names a field meets an argument of this
    function. It is how sphinx-needs' need directives, ``list2need`` and
    ``needservice``, sphinx-codelinks' one-line needs and sphinx-test-reports' needs are
    created; ``needimport``, ``needs_external_needs`` and sphinx-codelinks' multi-line
    needs are created from records, through the same path.

    .. code-block:: python

        from sphinx.util.docutils import SphinxDirective

        from sphinx_needs.api import NeedItemSource, create_need


        class ReqDirective(SphinxDirective):
            def run(self):
                need, need_nodes = create_need(
                    self.env.app,
                    self.state,
                    NeedItemSource.from_directive(self),
                    "req",
                    "A requirement",
                    id="REQ_1",
                    fields={"status": "open", "priority": "high"},
                    links={"links": ["REQ_0"]},
                )
                return need_nodes

    :param app: Sphinx application object.
    :param state: The parser state of the document the need is rendered in; ``None``
        only for an external source, whose need has no nodes.
    :param source: Where the need comes from: a
        :class:`~sphinx_needs.need_item.NeedItemSource`, or any object with the
        :class:`~sphinx_needs.need_item.NeedItemSourceProtocol` interface. It gives the
        need its ``docname``, ``lineno`` and the other location fields, and says whether
        it is imported or external. In a directive it is
        ``NeedItemSource.from_directive(self)``, as above; for a need on the page at
        a line the caller gives (the directive's parser line, as ``add_need`` took
        it), ``NeedItemSource.on_page(docname, lineno=lineno)``. Those two spellings
        are stable; ``NeedItemSource``'s general constructor and its keywords are
        provisional.
    :param need_type: The need type, by the name of its directive.
    :param title: The need's title.
    :param id: The need's id. If not given, one is generated (see
        :func:`generate_need_id`).
    :param fields: The need's field values, by field name: the core fields the field
        schema declares, such as ``status``, ``tags``, ``hide`` or ``template``
        (``title`` is an argument of its own), and the fields the project declares
        (:ref:`needs_fields`). A value ``None`` is a value not given, so a default
        applies.
    :param links: The need's links, by link type (:ref:`needs_links`): a string of
        comma separated ids, or a list of ids.
    :param content: The need's content, either as a ``str`` or a ``StringList`` (a
        string with mapping to the source text), parsed by the parser of the document
        the need is created in; or as a :class:`~sphinx_needs.api.MarkupContent`, the
        content with the markup it is written in. See :ref:`api_content_markup`.
    :param doctype: The source suffix the need is recorded as written in (e.g.
        ``".rst"``). If not given, it is the ``markup`` of a ``MarkupContent`` content,
        else the suffix of the document the need is created in.
    :param jinja_content: If true, the content is rendered as a Jinja template first.
    :param full_title: The title before it was trimmed, if it was: the generated id is
        derived from it.
    :param allow_type_coercion: If true, values are coerced to the type of their field
        where possible.
    :return: The need, as it is recorded in the project (the object, not a copy), and
        the nodes to insert into the document (none for an external need). The need is
        the one created in this read of the document: in a parallel build (``-j``) the
        merge of the processes' needs may still drop it, for an id another process
        created too.
    :raises InvalidNeedException: If the need is refused, before anything is recorded:
        for a value its field or link type refuses, an id that is missing, invalid or
        taken, a ``MarkupContent`` whose ``markup`` names no reStructuredText or MyST
        parser of the project, and any other validation the need fails, such as an
        unknown need type, a constraint not in :ref:`needs_constraints`, a template that
        does not exist, or Jinja content that does not render; (type
        ``invalid_kwargs``) for a name in ``fields`` or ``links`` the project does not
        declare, or one given in the wrong place: a link type in ``fields``, a field in
        ``links``, or one of this function's own arguments (``title``, ``content``, ...)
        in either.
    :raises ValueError: If ``state`` is ``None`` for a source that is not external.

    .. versionadded:: 9.2.0
    """
    if state is None and not source.dict_repr["is_external"]:
        raise ValueError("a parser state is required for a need that is not external")
    schema = SphinxNeedsData(app.env).get_schema()
    fields = fields or {}
    links = links or {}
    link_names = set(schema.iter_link_field_names())
    if misplaced := sorted(fields.keys() & link_names):
        raise InvalidNeedException(
            "invalid_kwargs",
            f"{misplaced!r} are link types: give them in 'links', not in 'fields'.",
        )
    #: what ``fields`` takes: the field schema's core fields (``title`` excepted, an
    #: argument of its own) and the extra fields
    field_names = {
        *schema.iter_core_field_names(),
        *schema.iter_extra_field_names(),
    } - {"title"}
    if misplaced := sorted(links.keys() & field_names):
        raise InvalidNeedException(
            "invalid_kwargs",
            f"{misplaced!r} are fields: give them in 'fields', not in 'links'.",
        )
    # a name of one of the need's values this function takes as an argument, unless
    # the project declares a field or a link type of that name
    arguments = _NEED_VALUE_ARGUMENTS - field_names - link_names
    for given, mapping in ((fields, "fields"), (links, "links")):
        if misplaced := sorted(given.keys() & arguments):
            raise InvalidNeedException(
                "invalid_kwargs",
                f"{misplaced[0]!r} is an argument of create_need: give it as "
                f"{misplaced[0]}=, not in {mapping!r}."
                if len(misplaced) == 1
                else f"{misplaced!r} are arguments of create_need: give them as "
                f"{', '.join(name + '=' for name in misplaced)}, not in {mapping!r}.",
            )
    return _create_need(
        app,
        state,
        source,
        need_type,
        title,
        values={**fields, **links},
        id=id,
        content=content,
        doctype=doctype,
        jinja_content=jinja_content,
        full_title=full_title,
        allow_type_coercion=allow_type_coercion,
    )


def _split_values(
    schema: FieldsSchema, values: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """A flat mapping of a need's field and link values as :func:`create_need`'s
    ``(fields, links)``: the project's link types to ``links``, the rest to ``fields``
    (a field and a link type never share a name).

    For this package's producers that hold the two in one mapping, as the options of a
    ``list2need`` item or a service's datum do.
    """
    link_names = set(schema.iter_link_field_names())
    fields = {k: v for k, v in values.items() if k not in link_names}
    links = {k: v for k, v in values.items() if k in link_names}
    return fields, links


_NEED_VALUE_ARGUMENTS = frozenset(
    ("title", "id", "content", "doctype", "jinja_content", "full_title")
)
"""The arguments of :func:`create_need` that are values of the need, which a name in its
``fields`` or ``links`` is refused as, naming the argument, unless the project declares
it. Its other arguments (``app``, ``state``, ``source``, ...) are the caller's, and a
field of their name is an unknown name like any other."""


def _create_need(
    app: Sphinx,
    state: RSTState | None,
    source: NeedItemSourceProtocol,
    need_type: str,
    title: str,
    *,
    values: Mapping[str, Any],
    id: str | None = None,
    content: str | StringList | MarkupContent = "",
    doctype: str | None = None,
    jinja_content: bool | None = None,
    full_title: str | None = None,
    allow_type_coercion: bool = True,
    parts: dict[str, NeedsPartType] | None = None,
    arch: dict[str, str] | None = None,
    signature: str | None = None,
    sections: Sequence[str] | None = None,
    external_css: str | None = "external_link",
) -> tuple[NeedItem, list[nodes.Node]]:
    """The one creation path: generate the need, record it, render its nodes.

    Every entry point comes here: :func:`create_need`, :func:`add_need`,
    :func:`ingest_need_record`, :func:`add_external_need` and the external needs
    reader. The fields and links are ``values``, one mapping (see
    :func:`_generate_need`), never keyword arguments. ``parts``, ``arch``,
    ``signature``, ``sections`` and ``external_css`` are computed for a need placed on
    a page, so only the record paths and :func:`add_need` give them.
    """
    if isinstance(source, NeedItemSource):
        # what the source's own producer could not record: the file of a page given
        # with no path (``NeedItemSource.on_page``, ``add_need``'s default source)
        hops = with_page_paths(source.hops, app.env.srcdir, app.env.doc2path)
        if hops is not source.hops:
            source = source._with_hops(hops)
    content_parser: type[Parser] | None = None
    content_source: tuple[str, int] | None = None
    if isinstance(content, MarkupContent):
        content_parser = resolve_content_parser(app, content.markup)
        content_source = content.source
        if doctype is None:
            doctype = content.markup
        content = content.text

    if (
        doctype is None
        and not source.dict_repr["is_external"]
        and (_docname := source.dict_repr["docname"])
    ):
        doctype = os.path.splitext(app.env.doc2path(_docname))[1]

    needs_info = _generate_need(
        NeedsSphinxConfig(app.config),
        SphinxNeedsData(app.env).get_schema(),
        need_type,
        title,
        source=source,
        values=values,
        id=id,
        doctype=doctype or "",
        content=_content_text(content),
        parts=parts,
        arch=arch,
        signature=signature,
        sections=sections,
        jinja_content=jinja_content,
        template_root=Path(str(app.srcdir)),
        external_css=external_css,
        full_title=full_title,
        allow_type_coercion=allow_type_coercion,
    )

    data = SphinxNeedsData(app.env)
    if (existing := data.get_needs_mutable().get(needs_info["id"])) is not None:
        if existing["is_external"] and not needs_info["is_external"]:
            # a need of this project (on a page, or imported) replaces an external need
            # of its id: what is authored here wins over what lives elsewhere
            data.remove_need(needs_info["id"])
            log_warning(
                logger,
                f"Need {needs_info['id']!r} replaces the external need of the same id "
                f"from {existing['external_url']}",
                "create_need",
                location=(needs_info["docname"], needs_info["lineno"])
                if needs_info["docname"]
                else None,
            )
        else:
            if id is None:
                # this is a generated ID
                message = f"Unique ID could not be generated for need with title {needs_info['title']!r}"
            else:
                message = f"A need with ID {needs_info['id']!r} already exists"
            raise InvalidNeedException(
                "duplicate_id", f"{message}{_defined_where(existing)}."
            )

    data.add_need(needs_info)

    if needs_info["is_external"]:
        return needs_info, []

    assert state is not None, "parser state must be set if need is not external"

    if needs_info["jinja_content"] or needs_info["template"]:
        # if the content was generated by jinja,
        # then we can no longer use the original potentially source mapped StringList
        content = needs_info["content"]

    return needs_info, _create_need_node(
        needs_info,
        app.env,
        state,
        content,
        content_parser=content_parser,
        content_source=content_source,
    )


def _defined_where(need: NeedItem) -> str:
    """Where an existing need is defined, as a parenthesised suffix of a message."""
    if need["is_external"]:
        return f" (external, {need['external_url']})"
    if not (docname := need["docname"]):
        return ""
    where = f"{docname}:{need['lineno']}" if need["lineno"] else docname
    if need["is_import"]:
        return f" (imported at {where})"
    return f" (defined at {where})"


RecordReader = Literal["import", "external"]
"""Which reader a needs.json record is read by: a ``needimport`` directive, or an
external source of ``needs_external_needs``."""


def _import_key_sets(
    needs_schema: FieldsSchema, *, reader: RecordReader = "import"
) -> tuple[set[str], set[str]]:
    """The keys a need record may carry in this project, and those never read.

    The core fields a reader omits are the ``exclude_import`` or ``exclude_external``
    column of ``NeedsCoreFields``; the two differ on ten fields. An imported need is
    rendered on the importing page, so it keeps how it is rendered (``collapse``,
    ``hide``, ``layout``, ``style``, ``jinja_content`` and the templates) and takes its
    ``sections`` and ``signature`` from that page; an external need lives elsewhere, so
    it keeps the latter and drops the former.

    :param reader: Which reader the record is read by.
    :return: ``(known, omitted)``: every need field the project knows (core fields,
        links and their ``_back`` names, extra fields, and the legacy ``full_title``),
        and the subset that is computed rather than read.
    """
    flag = "exclude_import" if reader == "import" else "exclude_external"
    link_names = list(needs_schema.iter_link_field_names())
    extra_names = set(needs_schema.iter_extra_field_names())
    known = {
        "full_title",  # legacy
        *NeedsCoreFields,
        *link_names,
        *(f"{x}_back" for x in link_names),
        *extra_names,
    }
    omitted = {
        # legacy, unless the project declares a field of that name (#2392)
        *({"full_title"} - extra_names),
        *(k for k, v in NeedsCoreFields.items() if v.get(flag)),
        *(f"{x}_back" for x in link_names),
    }
    return known, omitted


def _need_record_params(
    record: Mapping[str, Any],
    needs_schema: FieldsSchema,
    *,
    reader: RecordReader = "import",
) -> tuple[dict[str, Any], set[str]]:
    """The creation parameters of a needs.json-style record: its keys that the project
    reads, ``type`` defaulting to ``""`` (see :func:`_create_from_record`).

    :param reader: Which reader the record is read by: the core fields it omits.
    :return: The parameters, and the record's keys the project does not know (dropped).
    """
    params = dict(record)
    map_legacy_keys(params)
    # Remove unknown keys, as they may be defined in the source system, but not in this
    # project, and the keys that are computed rather than read; the keys of the
    # record's need type (a type that is not a string is refused later)
    need_type = params.get("type")
    known, omitted = _import_key_sets(
        needs_schema.for_type(need_type if isinstance(need_type, str) else None),
        reader=reader,
    )
    unknown: set[str] = set()
    for key in list(params):
        if key not in known:
            # every needs.json written before the GitHub services were registered only
            # when configured carries their fields on each need, null (or "" in older
            # files) where no service made it: an empty one is no data to lose
            if not (key in GITHUB_FIELDS and params[key] in (None, "")):
                unknown.add(key)
            del params[key]
        elif key in omitted:
            del params[key]
    params.setdefault("type", "")
    return params, unknown


def _check_record_params(params: Mapping[str, Any]) -> None:
    """Refuse a record whose values the creation reads before it validates any field.

    :raises InvalidNeedException: If its ``id`` is given but empty or not a string, its ``title``
        is missing or not a string, its ``content`` or ``type`` not a string, or its
        ``parts`` not a mapping of mappings.
    """
    if (need_id := params.get("id")) is not None and not isinstance(need_id, str):
        raise InvalidNeedException(
            "invalid_id", f"id must be a string, not {type(need_id).__name__}"
        )
    if need_id == "":
        raise InvalidNeedException("invalid_id", "id is empty")
    if "title" not in params:
        raise InvalidNeedException("invalid_value", "title is missing")
    if not isinstance(params["title"], str):
        raise InvalidNeedException(
            "invalid_value",
            f"title must be a string, not {type(params['title']).__name__}",
        )
    if "content" in params and not isinstance(params["content"], str):
        raise InvalidNeedException(
            "content",
            f"content must be a string, not {type(params['content']).__name__}",
        )
    if not isinstance(params["type"], str):
        raise InvalidNeedException(
            "invalid_type",
            f"type must be a string, not {type(params['type']).__name__}",
        )
    if (parts := params.get("parts")) is not None:
        if not isinstance(parts, Mapping):
            raise InvalidNeedException(
                "parts", f"parts must be a mapping, not {type(parts).__name__}"
            )
        for part_id, part in parts.items():
            if not isinstance(part, Mapping):
                raise InvalidNeedException(
                    "parts",
                    f"part {part_id!r} must be a mapping, not {type(part).__name__}",
                )


def _record_params(
    record: Mapping[str, Any],
    needs_schema: FieldsSchema,
    *,
    reader: RecordReader,
    unknown_keys: set[str] | None = None,
) -> tuple[dict[str, Any], set[str]]:
    """The one record path of both needs.json readers: a record's creation
    parameters, checked.

    :param reader: Which reader the record is read by.
    :param unknown_keys: If given, the record's keys unknown to the project are added
        to it before the record is checked, so a caller collecting them over several
        records has them also for a record that is refused.
    :return: The parameters, and the record's keys the project does not know (dropped).
    :raises InvalidNeedException: What :func:`_check_record_params` raises.
    """
    params, unknown = _need_record_params(record, needs_schema, reader=reader)
    if unknown_keys is not None:
        unknown_keys.update(unknown)
    _check_record_params(params)
    return params, unknown


def ingest_need_record(
    app: Sphinx,
    state: RSTState,
    record: Mapping[str, Any],
    *,
    need_source: NeedItemSourceProtocol,
    content_markup: str | None = None,
    content_source: tuple[str, int] | None = None,
    allow_type_coercion: bool = True,
    unknown_keys: set[str] | None = None,
) -> tuple[list[nodes.Node], set[str]]:
    """Create one need from a needs.json-style record.

    This is the path for needs that come from outside the page they are rendered on;
    :ref:`needimport <needimport>` creates each of its needs through it.

    ``record`` holds the keys a need object has in ``needs.json``: ``type``, ``title``,
    ``id``, fields and links as authored, ``content``, ``doctype``, and so on.
    It is not modified. A legacy ``description`` is taken as the ``content`` when that is
    empty; keys the project does not know are dropped and returned; keys that are
    computed rather than imported (such as ``docname``, ``lineno``, ``full_title`` or
    the ``<link>_back`` names) are dropped silently. The need is created from the rest
    through the same path as :func:`create_need`: ``type`` as its ``need_type``, and
    its fields and links as one mapping, so a record key named like an argument of
    that path is the field of its name.

    :param app: The Sphinx application.
    :param state: The parser state of the document the need is rendered in.
    :param record: The need record.
    :param need_source: Where the need is recorded as coming from, e.g.
        ``NeedItemSource(hops, lineno=lineno, is_import=True)`` for a need read from a
        file.
    :param content_markup: The source suffix of the markup the record's ``content`` is
        written in: given, the content is created as a
        :class:`~sphinx_needs.api.MarkupContent` with this ``markup``, and the need
        records it as its ``doctype`` if the record has none.
    :param content_source: The ``source`` of that ``MarkupContent``: ``(path,
        first_line)`` of the content. Only meaningful with ``content_markup``.
    :param allow_type_coercion: As for :func:`create_need`.
    :param unknown_keys: If given, the record's keys that are unknown to the project
        are added to it before the need is created, so a caller collecting them over
        several records has them also for a record whose need cannot be created.
    :return: The need's nodes, and the set of the record's keys that were dropped as
        unknown to the project (the caller decides whether to warn about them).
    :raises InvalidNeedException: What :func:`create_need` raises; (type ``content``) if
        the record's ``content`` (or the legacy ``description`` taken as it) is present
        but not a string; (type ``invalid_type``) if its ``type`` is not a string;
        (type ``invalid_value``) if its ``title`` is missing or not a string; (type
        ``invalid_id``) if its ``id`` is given but empty or not a string; (type ``parts``) if its
        ``parts`` is not a mapping of mappings; and (type ``content_markup``) if
        ``content_source`` is given without ``content_markup``. The caller decides how
        to report it.

    .. versionadded:: 9.0.0
    """
    params, unknown = _record_params(
        record,
        SphinxNeedsData(app.env).get_schema(),
        reader="import",
        unknown_keys=unknown_keys,
    )
    if content_markup is not None:
        params["content"] = MarkupContent(
            params.get("content", ""), markup=content_markup, source=content_source
        )
    elif content_source is not None:
        raise InvalidNeedException(
            "content_markup",
            "content_source is only meaningful together with content_markup.",
        )
    _, need_nodes = _create_from_record(
        app,
        state,
        params,
        source=need_source,
        allow_type_coercion=allow_type_coercion,
    )
    return need_nodes, unknown


def _create_from_record(
    app: Sphinx,
    state: RSTState | None,
    params: dict[str, Any],
    *,
    source: NeedItemSourceProtocol,
    allow_type_coercion: bool = True,
) -> tuple[NeedItem, list[nodes.Node]]:
    """Create a need from a record's parameters (:func:`_record_params`), as both
    needs.json readers do.

    The keys that are arguments of :func:`_create_need` are taken out of ``params``,
    which is consumed; the rest are its fields and links. Each of those keys is a core
    field, which no field of the project can be named like.
    """
    return _create_need(
        app,
        state,
        source,
        params.pop("type"),
        params.pop("title"),
        id=params.pop("id", None),
        content=params.pop("content", ""),
        doctype=params.pop("doctype", None),
        jinja_content=params.pop("jinja_content", None),
        parts=params.pop("parts", None),
        arch=params.pop("arch", None),
        signature=params.pop("signature", None),
        sections=params.pop("sections", None),
        # ``None``: the default css class (``_generate_need`` holds it)
        external_css=params.pop("external_css", None),
        allow_type_coercion=allow_type_coercion,
        values=params,
    )


def _template_parse_offset(data: NeedItem) -> int:
    """The offset at which to parse a need's rendered ``pre``/``post`` template content.

    That content exists in no file, so the only sensible place to anchor a warning
    raised inside it is the need's own directive. ``nested_parse`` resolves a nested
    parse's locations through the *enclosing* state machine
    (``abs_line_number()`` = ``line_offset + input_offset + 1``), so the anchor has to be
    given in that machine's line space -- the same space ``lineno_content`` is kept in,
    and **not** the resolved source line a need records since #1349. A need directive
    keeps the unresolved number as ``parser_lineno`` for exactly this; every other kind
    of source still stores it in ``lineno`` itself.
    """
    source = data.source
    parser_lineno = source.parser_lineno if isinstance(source, NeedItemSource) else None
    if parser_lineno is None:
        parser_lineno = data["lineno"]
    return (parser_lineno - 1) if parser_lineno else 0


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


def _host_content_anchor(
    state: RSTState, input_offset: int, host_source: str, need_line: int | None
) -> tuple[str, int]:
    """Where the host's own ``nested_parse`` at ``input_offset`` reports its first line.

    :param input_offset: A 0-based line in the parser's line space (a directive's
        ``self.content_offset``, or its ``self.lineno - 1``).
    :param need_line: The need's own line, the anchor when ``input_offset`` is not a
        line of the input the state machine is parsing.
    :return: ``(source, 1-based line)``.
    """
    source: str | None = None
    line: int | None = None
    if isinstance(state, RSTState):
        # docutils: the offset is a line in the parser's own space, which ``rst_prolog``
        # and ``.. include::`` shift; the state machine maps it back to a file line.
        # The machine may be a nested one, covering only part of the page: a line
        # outside its input would map to another line of it (a negative index counts
        # from its end), so such a line is not mapped
        machine = state.state_machine
        input_lines = machine.input_lines or ()
        if 0 <= input_offset - machine.input_offset < len(input_lines):
            source, line = machine.get_source_and_line(input_offset + 1)
        else:
            return host_source, need_line or input_offset + 1
    else:
        # myst-parser's ``MockState.nested_parse`` offsets from the directive's own line,
        # which is what its state machine reports when asked for no line in particular
        source, line = state.state_machine.get_source_and_line()
        line = None if line is None else line + input_offset + 1
    return (str(source) if source else host_source), (
        line if line is not None else input_offset + 1
    )


def _parse_declared_content(
    data: NeedItem,
    state: RSTState,
    content: str | StringList,
    content_offset: int,
    node: nodes.Element,
    *,
    parser: type[Parser],
    content_source: tuple[str, int] | None,
    host_source: str,
) -> None:
    """Parse a need's content in the markup of the ``MarkupContent`` it was given as."""
    # a file's lines are what ``\n`` separates: not ``str.splitlines``, which also
    # breaks on a form feed and the like; and a ``\r`` ending a line (CRLF text, or
    # lines split from it on ``\n``) is not part of it
    lines = [
        line.removesuffix("\r")
        for line in (
            content if isinstance(content, StringList) else content.split("\n")
        )
    ]
    if data["jinja_content"] or data["template"]:
        # rendered text exists in no file: anchor it at the need's own line, as the
        # pre/post template content is
        if isinstance(state, RSTState):
            source, first_line = _host_content_anchor(
                state, _template_parse_offset(data), host_source, data["lineno"]
            )
        else:
            # ``_template_parse_offset`` is a line of the page, while myst-parser's
            # nested parse offsets from the directive's line: the need's own line is
            # already the page line wanted
            source, first_line = host_source, data["lineno"] or 1
    elif content_source is not None:
        source, first_line = content_source
    else:
        source, first_line = _host_content_anchor(
            state, content_offset, host_source, data["lineno"]
        )
    parse_need_content(
        state, lines, parser=parser, source=source, first_line=first_line, node=node
    )


def _create_need_node(
    data: NeedItem,
    env: BuildEnvironment,
    state: RSTState,
    content: str | StringList,
    *,
    content_parser: type[Parser] | None = None,
    content_source: tuple[str, int] | None = None,
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
    :param content_parser: If given, the content is parsed by this parser (the one
        resolved for a ``MarkupContent``'s markup) rather than by ``state``.
    :param content_source: ``(path, first_line)`` of the content, used with ``content_parser``.
    """
    source = env.doc2path(data["docname"]) if data["docname"] else None

    style_classes = ["need", f"need-{data['type'].lower()}"]
    if data["style"]:
        style_classes.append(data["style"])

    node_need = Need("", classes=style_classes, ids=[data["id"]], refid=data["id"])
    node_need.source, node_need.line = source, data["lineno"]
    # the document whose need this node renders: under ``-j N`` two documents read by
    # different workers can each create a need with the same id, and the merge keeps
    # only one of them, so ``format_need_nodes`` renders a node only if its need is
    # still recorded on the document the node was written in (#2087). ``node.source``
    # cannot say which document that is in general, and the name ``doctree-resolved``
    # passes is the root document's for ``singlehtml`` and ``latex``. The node is
    # replaced before any writer sees it, so the attribute reaches no output.
    node_need["docname"] = data["docname"]

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
                _template_parse_offset(data),
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
    if content_parser is not None:
        _parse_declared_content(
            data,
            state,
            content,
            content_offset,
            node_need,
            parser=content_parser,
            content_source=content_source,
            host_source=str(source) if source else "",
        )
    elif isinstance(content, StringList):
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
                _template_parse_offset(data),
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
    for fixed_key in ("docname", "lineno", "is_external"):
        if fixed_key in kwargs:
            kwargs.pop(fixed_key)
            # TODO Although it seems prudent to not silently ignore user input here,
            # raising an error here currently breaks some existing tests
            # raise ValueError(
            #     f"{fixed_key} is not allowed in kwargs for add_external_need"
            # )
    schema = SphinxNeedsData(app.env).get_schema()
    if "state" in kwargs and "state" not in {
        *schema.iter_extra_field_names(),
        *schema.iter_link_field_names(),
    }:
        # ``add_need``'s parser state, which an external need has none of: dropped as
        # before, but a field of the project of that name is a field (#2403)
        kwargs.pop("state")
    if kwargs.keys() & _deprecated_kwargs:
        # as ``add_need``, which this function called, warns of them
        warnings.warn(
            "deprecated key found in kwargs", DeprecationWarning, stacklevel=1
        )
        kwargs = {k: v for k, v in kwargs.items() if k not in _deprecated_kwargs}
    # a key naming one of ``add_need``'s other keywords is that keyword, as when this
    # function called it; the rest are the need's fields and links
    keywords = {k: kwargs.pop(k) for k in _ADD_NEED_KEYWORDS if k in kwargs}
    _, need_nodes = _create_need(
        app,
        None,
        _legacy_source(
            need_source,
            lineno_content=keywords.pop("lineno_content", None),
            is_import=keywords.pop("is_import", False),
            is_external=True,
            external_url=external_url,
        ),
        need_type,
        # TODO a title being None is not "type compatible" with other parts of the code base,
        # however, at present changing it to an empty string breaks some existing tests.
        title,  # ty: ignore[invalid-argument-type]
        values={"status": status, "tags": tags, "constraints": constraints, **kwargs},
        id=id,
        content=content,
        doctype=keywords.get("doctype"),
        jinja_content=keywords.get("jinja_content"),
        full_title=keywords.get("full_title"),
        allow_type_coercion=keywords.get("allow_type_coercion", True),
        parts=keywords.get("parts"),
        arch=keywords.get("arch"),
        signature=keywords.get("signature"),
        sections=keywords.get("sections"),
        external_css=external_css,
    )
    return need_nodes


_ADD_NEED_KEYWORDS = (
    "lineno_content",
    "is_import",
    "doctype",
    "jinja_content",
    "full_title",
    "allow_type_coercion",
    "parts",
    "arch",
    "signature",
    "sections",
)
"""The keywords of :func:`add_need` that :func:`add_external_need` takes from its
``**kwargs`` as keywords rather than as fields, as it did when it called
:func:`add_need`: those it does not name itself, and that are no field of the field
schema."""


def _prepare_template(
    needs_config: NeedsSphinxConfig,
    needs_info: NeedItem,
    template_name: str,
    template_root: Path | None,
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
        new_content = render_template_string(
            template_content,
            {**needs_info.filter_context(), **needs_config.render_context},
            autoescape=False,
        )
    except Exception as e:
        raise InvalidNeedException(
            "invalid_template",
            f"Error while rendering template {template_path}: {e}",
        ) from e

    return new_content


def generate_need_id(
    app: Sphinx,
    need_type: str,
    title: str,
    content: str | StringList | MarkupContent = "",
    *,
    full_title: str | None = None,
) -> str:
    """Return the id :func:`create_need` (and :func:`add_need`) assigns to a need that
    is given no ``id``.

    The arguments are those of the same name given to :func:`create_need`, which
    derives the id with this same code: the type's ``prefix``, followed by a hash of
    ``full_title`` (if given, else ``title``), or of ``content`` when that is empty,
    shaped by :ref:`needs_id_from_title` and :ref:`needs_id_length`.
    An extension that creates needs can use it to find out, before it calls
    :func:`create_need`, whether a need with that id already exists.

    The id is not checked: :func:`create_need` may still refuse the need, for example
    because :ref:`needs_id_required` is set, the id does not match
    :ref:`needs_id_regex`, or a need with that id already exists.

    :param app: Sphinx application object.
    :param need_type: Name of the need type, as given to :func:`create_need`.
    :param title: Title of the need.
    :param content: Content of the need, either as a ``str``
        or a ``StringList``, as :func:`create_need` takes it.
    :param full_title: The untrimmed title, if ``title`` was trimmed.
    :return: The generated id.
    :raises InvalidNeedException: If ``need_type`` is not a configured need type
        (type ``invalid_type``, as :func:`create_need` raises it).
    """
    needs_config = NeedsSphinxConfig(app.config)
    return _generate_need_id(
        needs_config,
        _get_need_type(needs_config, need_type)["prefix"],
        title,
        _content_text(content),
        full_title,
    )


def _content_text(content: str | StringList | MarkupContent) -> str:
    """A need's content as the text :func:`generate_need` is given, whether it came as
    a ``str``, a ``StringList``, or the ``text`` of a ``MarkupContent``."""
    if isinstance(content, MarkupContent):
        content = content.text
    return "\n".join(content) if isinstance(content, StringList) else content


def _get_need_type(needs_config: NeedsSphinxConfig, need_type: str) -> NeedType:
    """The configuration of a need type, by its directive name.

    :raises InvalidNeedException: If the type is not configured.
    """
    configured_need_types = {ntype["directive"]: ntype for ntype in needs_config.types}
    if not (need_type_data := configured_need_types.get(need_type)):
        raise InvalidNeedException("invalid_type", f"Unknown need type {need_type!r}.")
    return need_type_data


def _generate_need_id(
    needs_config: NeedsSphinxConfig,
    type_prefix: str,
    title: str,
    content: str,
    full_title: str | None,
) -> str:
    """The id of a need given no ``id``: the one derivation behind both
    :func:`generate_need` and :func:`generate_need_id`."""
    return _make_hashed_id(
        type_prefix,
        title if full_title is None else full_title,
        content,
        needs_config,
    )


def _make_hashed_id(
    type_prefix: str, full_title: str, content: str, config: NeedsSphinxConfig
) -> str:
    """Create an ID based on the type and title of the need.

    Private. Kept for the published sibling packages, which import it
    (sphinx-codelinks 2.0.x; sphinx-test-reports up to 3.0.x, including its uncapped
    1.x and 2.0.0); removed in 10.0. New code calls :func:`generate_need_id`.
    """
    hashable_content = full_title or content
    hashed = hashlib.sha1(hashable_content.encode("UTF-8")).hexdigest().upper()
    if config.id_from_title:
        hashed = full_title.upper().replace(" ", "_") + "_" + hashed
    return f"{type_prefix}{hashed[: config.id_length]}"


def _copy_links(
    links: dict[str, LinksLiteralValue | LinksFunctionArray | None],
    schema: TypeFieldsSchema,
) -> None:
    """Implement 'copy' logic for links, on the schema of the need's type.

    The link types copied are :meth:`~.FieldsSchema.copying_link_types`: nothing is
    copied into a derived ``links``, which holds what its rule computes, nor from a
    derived link type, whose ``copy`` is refused at load.
    """
    if "links" not in links:
        return  # should not happen, but be defensive
    copy_links: list[
        NeedLink | DynamicFunctionParsed | VariantFunctionParsed | VariantDataParsed
    ] = []
    for name in schema.copying_link_types():
        other = links[name]
        if isinstance(other, LinksLiteralValue | LinksFunctionArray):
            copy_links.extend(other.value)
    if any(
        isinstance(
            li, DynamicFunctionParsed | VariantFunctionParsed | VariantDataParsed
        )
        for li in copy_links
    ):
        if links["links"] is None:
            links["links"] = LinksFunctionArray(tuple(copy_links))
        else:
            links["links"] = LinksFunctionArray(
                tuple(links["links"].value) + tuple(copy_links)
            )
    else:
        copy_links_literal = [li for li in copy_links if isinstance(li, NeedLink)]
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
    location: tuple[str | None, int | None] | None


_PredicateValue = TypeVar("_PredicateValue")


def _match_predicate_default(
    predicate_defaults: Sequence[tuple[str, _PredicateValue]],
    config_name: str,
    field_name: str,
    config: NeedsSphinxConfig,
    core: PredicateContextData,
    extras: dict[str, AllowedTypes | None],
    links: dict[str, list[str]],
    location: tuple[str | None, int | None] | None,
) -> _PredicateValue | None:
    """Return the value of the first predicate that matches this need, if any.

    A predicate that cannot be evaluated is reported and skipped:
    it used to raise out of the need's creation and end the whole build with a
    traceback, so a single mistake in the configuration cost the project every need.
    The remaining predicates are still evaluated, and if none of them matches then
    the caller falls back to the plain ``default``, exactly as an unmatched
    predicate has always done.
    """
    for predicate, value in predicate_defaults:
        try:
            matched = apply_default_predicate(predicate, config, core, extras, links)
        except NeedsInvalidFilter as err:
            # once=True: a configuration mistake that breaks the expression outright
            # would otherwise be repeated for every need in the project. The dedup
            # key is the whole message, so a predicate that fails only for SOME
            # needs, or for different reasons on different needs, is still reported
            # once per distinct error -- evaluability is data-dependent, which is
            # why the predicate must keep being evaluated per need rather than
            # being marked broken and skipped wholesale.
            log_warning(
                logger,
                f"{config_name}[{field_name!r}]['predicates']: {err} "
                "The predicate is skipped.",
                "config",
                location,
                once=True,
            )
            continue
        if matched:
            return value
    return None


def _get_field_default(
    scheme: FieldSchema | None,
    config: NeedsSphinxConfig,
    core: PredicateContextData,
    extras: dict[str, AllowedTypes | None],
    links: dict[str, list[str]],
    location: tuple[str | None, int | None] | None,
) -> FieldLiteralValue | FieldFunctionArray | None:
    if scheme is None:
        return None  # TODO except (and catch upstream)
    # TODO if we stored default lists as tuples we could avoid the deepcopy here
    if (
        value := _match_predicate_default(
            scheme.predicate_defaults,
            "needs_fields",
            scheme.name,
            config,
            core,
            extras,
            links,
            location,
        )
    ) is not None:
        return deepcopy(value)
    if scheme.default is not None:
        return deepcopy(scheme.default)
    return None


def _get_links_default(
    scheme: LinkSchema | None,
    config: NeedsSphinxConfig,
    core: PredicateContextData,
    extras: dict[str, AllowedTypes | None],
    links: dict[str, list[str]],
    location: tuple[str | None, int | None] | None,
) -> LinksLiteralValue | LinksFunctionArray | None:
    if scheme is None:
        return None  # TODO except (and catch upstream)
    # TODO if we stored default lists as tuples we could avoid the deepcopy here
    if (
        value := _match_predicate_default(
            scheme.predicate_defaults,
            "needs_links",
            scheme.name,
            config,
            core,
            extras,
            links,
            location,
        )
    ) is not None:
        return deepcopy(value)
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
