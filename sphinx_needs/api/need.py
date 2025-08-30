from __future__ import annotations

import hashlib
import os
import re
import warnings
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, TypeVar

from docutils import nodes
from docutils.parsers.rst.states import RSTState
from docutils.statemachine import StringList
from jinja2 import Template
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, NeedsPartType, SphinxNeedsData
from sphinx_needs.directives.needuml import Needuml, NeedumlException
from sphinx_needs.exceptions import InvalidNeedException
from sphinx_needs.filter_common import (
    PredicateContextData,
    apply_default_predicate,
)
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import (
    NeedItem,
    NeedItemSourceProtocol,
    NeedItemSourceUnknown,
    NeedsContent,
)
from sphinx_needs.nodes import Need
from sphinx_needs.roles.need_part import find_parts, update_need_with_parts
from sphinx_needs.utils import jinja_parse
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
    hide: None | bool = None,
    collapse: None | bool = None,
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
    **kwargs: str,
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

    # validate status
    if needs_config.statuses and status not in [
        stat["name"] for stat in needs_config.statuses
    ]:
        raise InvalidNeedException(
            "invalid_status", f"Status {status!r} not in 'needs_statuses'."
        )

    # validate tags
    tags = (
        [v for v, _ in _split_list_with_dyn_funcs(tags, location)]
        if tags is not None
        else None
    )
    if (
        tags is not None
        and needs_config.tags
        and (unknown_tags := set(tags) - {t["name"] for t in needs_config.tags})
    ):
        raise InvalidNeedException(
            "invalid_tags", f"Tags {unknown_tags!r} not in 'needs_tags'."
        )

    # validate constraints
    constraints = (
        [v for v, _ in _split_list_with_dyn_funcs(constraints, location)]
        if constraints is not None
        else None
    )
    if constraints is not None and (
        unknown_constraints := set(constraints) - set(needs_config.constraints)
    ):
        raise InvalidNeedException(
            "invalid_constraints",
            f"Constraints {unknown_constraints!r} not in 'needs_constraints'.",
        )

    extras_no_defaults = {
        # note, for backward-compatibility currently we convert all extra values to strings,
        # and warn in the import/external need code if they are not of type str
        key: str(kwargs[key]) if key in kwargs else None
        for key in needs_config.extra_options
    }
    links_no_defaults = {
        li["option"]: [
            v for v, _ in _split_list_with_dyn_funcs(kwargs[li["option"]], location)
        ]
        if li["option"] in kwargs
        else None
        for li in needs_config.extra_links
    }

    defaults_ctx: PredicateContextData = {
        "id": need_id,
        "type": need_type,
        "title": title,
        "tags": tuple(tags or []),
        "status": status,
        "docname": source.dict_repr["docname"],
        "is_import": source.dict_repr["is_import"],
        "is_external": source.dict_repr["is_external"],
    }
    defaults_extras = extras_no_defaults.copy()
    defaults_links = {k: tuple(v or []) for k, v in links_no_defaults.items()}

    status = _get_default_str_none(
        "status", status, needs_config, defaults_ctx, defaults_extras, defaults_links
    )
    tags = _get_default_list(
        "tags", tags, needs_config, defaults_ctx, defaults_extras, defaults_links
    )
    collapse = _get_default_bool(
        "collapse",
        collapse,
        needs_config,
        defaults_ctx,
        defaults_extras,
        defaults_links,
    )
    hide = _get_default_bool(
        "hide", hide, needs_config, defaults_ctx, defaults_extras, defaults_links
    )
    layout = _get_default_str_none(
        "layout", layout, needs_config, defaults_ctx, defaults_extras, defaults_links
    )
    style = _get_default_str_none(
        "style", style, needs_config, defaults_ctx, defaults_extras, defaults_links
    )
    template = _get_default_str_none(
        "template",
        template,
        needs_config,
        defaults_ctx,
        defaults_extras,
        defaults_links,
    )
    pre_template = _get_default_str_none(
        "pre_template",
        pre_template,
        needs_config,
        defaults_ctx,
        defaults_extras,
        defaults_links,
    )
    post_template = _get_default_str_none(
        "post_template",
        post_template,
        needs_config,
        defaults_ctx,
        defaults_extras,
        defaults_links,
    )
    constraints = _get_default_list(
        "constraints",
        constraints,
        needs_config,
        defaults_ctx,
        defaults_extras,
        defaults_links,
    )
    extras = _get_default_extras(
        extras_no_defaults, needs_config, defaults_ctx, defaults_extras, defaults_links
    )
    links = _get_default_links(
        links_no_defaults, needs_config, defaults_ctx, defaults_extras, defaults_links
    )
    _copy_links(links, needs_config)

    # Add the need and all needed information
    core_data: NeedsInfoType = {
        "type": need_type,
        "type_name": need_type_data["title"],
        "type_prefix": need_type_data["prefix"],
        "type_color": need_type_data.get("color") or "#000000",
        "type_style": need_type_data.get("style") or "node",
        "status": status,
        "tags": tags,
        "constraints": tuple(constraints),
        "id": need_id,
        "title": title,
        "collapse": collapse,
        "arch": arch or {},
        "style": style,
        "layout": layout,
        "hide": hide,
        "parts": parts or {},
        "external_css": external_css or "external_link",
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
        template=template,
        pre_template=pre_template,
        post_template=post_template,
        jinja_content=jinja_content or False,
    )

    needs_info = NeedItem(
        core=core_data,
        extras=extras,
        links=links,
        source=source,
        content=content_info,
        _validate=False,
    )

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

        needs_info.replace_content(content_info)

    return needs_info


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
    hide: None | bool = None,
    collapse: None | bool = None,
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
    :param external_uneeds_inforl: URL as string, which is used as target if ``is_external`` is ``True``
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


def _split_list_with_dyn_funcs(
    text: None | str | list[str],
    location: tuple[str, int | None] | None,
    warn_prefix: str = "",
) -> Iterable[tuple[str, bool]]:
    """Split a ``;|,`` delimited string that may contain ``[[...]]`` dynamic functions.

    :param text: The string to split.
        If the input is a list of strings, yield the list unchanged,
        or if the input is None, yield nothing.
    :param location: A location to use for emitting warnings about badly formatted strings.

    :yields: A tuple of the string and a boolean indicating if the string contains one or more dynamic function.
        Each string is stripped of leading and trailing whitespace,
        and only yielded if it is not empty.

    """
    if text is None:
        return

    if not isinstance(text, str):
        assert isinstance(text, list) and all(isinstance(x, str) for x in text), (
            "text must be a string or a list of strings"
        )
        yield from ((x, False) for x in text)
        return

    _current_element = ""
    _has_dynamic_function = False
    while text:
        if text.startswith("[["):
            _has_dynamic_function = True
            _current_element += text[:2]
            text = text[2:]
            while text and not text.startswith("]]"):
                _current_element += text[0]
                text = text[1:]
            if _current_element.endswith("]"):
                _current_element += "]"
            else:
                _current_element += "]]"
            if not text.startswith("]]"):
                log_warning(
                    logger,
                    f"Dynamic function not closed correctly: {text}{warn_prefix}",
                    "dynamic_function",
                    location=location,
                )
            text = text[2:]
        elif text[0] in ";|,":
            _current_element = _current_element.strip()
            if _current_element:
                yield _current_element, _has_dynamic_function
            _current_element = ""
            _has_dynamic_function = False
            text = text[1:]
        else:
            _current_element += text[0]
            text = text[1:]

    _current_element = _current_element.strip()
    if _current_element:
        yield _current_element, _has_dynamic_function


def _copy_links(links: dict[str, list[str]], config: NeedsSphinxConfig) -> None:
    """Implement 'copy' logic for links."""
    copy_links: list[str] = []
    for link_type in config.extra_links:
        if link_type.get("copy", False) and (name := link_type["option"]) != "links":
            copy_links += links[name]  # Save extra links for main-links
    links["links"] += copy_links  # Set copied links to main-links


def _get_default_str_none(
    key: str,
    value: str | None,
    config: NeedsSphinxConfig,
    context: PredicateContextData,
    extras: dict[str, str | None],
    links: dict[str, tuple[str, ...]],
) -> str | None:
    if value is not None:
        return value
    return _get_default(key, config, context, extras, links)


def _get_default_str(
    key: str,
    value: str | None,
    config: NeedsSphinxConfig,
    context: PredicateContextData,
    extras: dict[str, str | None],
    links: dict[str, tuple[str, ...]],
) -> str:
    if value is not None:
        return value
    if (_default_value := _get_default(key, config, context, extras, links)) is None:
        return ""
    else:
        assert isinstance(_default_value, str)
        return _default_value


_T = TypeVar("_T")


def _get_default_list(
    key: str,
    value: None | list[_T],
    config: NeedsSphinxConfig,
    context: PredicateContextData,
    extras: dict[str, str | None],
    links: dict[str, tuple[str, ...]],
) -> list[_T]:
    if value is not None:
        return value
    if (_default_value := _get_default(key, config, context, extras, links)) is None:
        return []
    else:
        assert isinstance(_default_value, list)
        return _default_value


def _get_default_bool(
    key: str,
    value: None | bool,
    config: NeedsSphinxConfig,
    context: PredicateContextData,
    extras: dict[str, str | None],
    links: dict[str, tuple[str, ...]],
    *,
    default: bool = False,
) -> bool:
    if value is not None:
        return value
    if (_default_value := _get_default(key, config, context, extras, links)) is None:
        return default
    else:
        assert isinstance(_default_value, bool)
        return _default_value


def _get_default_extras(
    value: dict[str, str | None],
    config: NeedsSphinxConfig,
    context: PredicateContextData,
    extras: dict[str, str | None],
    links: dict[str, tuple[str, ...]],
) -> dict[str, str]:
    return {
        key: _get_default_str(key, value[key], config, context, extras, links)
        for key in value
    }


def _get_default_links(
    value: dict[str, list[str] | None],
    config: NeedsSphinxConfig,
    context: PredicateContextData,
    extras: dict[str, str | None],
    links: dict[str, tuple[str, ...]],
) -> dict[str, list[str]]:
    return {
        key: _get_default_list(key, value[key], config, context, extras, links)
        for key in value
    }


def _get_default(
    key: str,
    config: NeedsSphinxConfig,
    context: PredicateContextData,
    extras: dict[str, str | None],
    links: dict[str, tuple[str, ...]],
) -> None | Any:
    if (defaults := config.field_defaults.get(key)) is None:
        return None
    for predicate, v in defaults.get("predicates", []):
        # use the first predicate that is satisfied
        if apply_default_predicate(predicate, config, context, extras, links):
            return v

    return defaults.get("default", None)


def get_needs_view(app: Sphinx) -> NeedsView:
    """Return a read-only view of all resolved needs.

    .. important:: this should only be called within the write phase,
        after the needs have been fully collected.
        If not already done, this will ensure all needs are resolved
        (e.g. back links have been computed etc),
        and then lock the data to prevent further modification.
    """
    return SphinxNeedsData(app.env).get_needs_view()
