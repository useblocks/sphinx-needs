from __future__ import annotations

import hashlib
import os
import re
import warnings
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from docutils import nodes
from docutils.parsers.rst.states import RSTState
from docutils.statemachine import StringList
from jinja2 import Template
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.api.exceptions import InvalidNeedException
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, NeedsPartType, SphinxNeedsData
from sphinx_needs.directives.needuml import Needuml, NeedumlException
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.logging import get_logger, log_warning
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
    signature: str = "",
    sections: list[str] | None = None,
    jinja_content: None | bool = False,
    hide: bool = False,
    collapse: None | bool = None,
    style: None | str = None,
    layout: None | str = None,
    template_root: Path | None = None,
    template: None | str = None,
    pre_template: str | None = None,
    post_template: str | None = None,
    is_external: bool = False,
    external_url: str | None = None,
    external_css: str = "external_link",
    full_title: str | None = None,
    **kwargs: str,
) -> NeedsInfoType:
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
    :param hide: boolean value.
    :param collapse: boolean value.
    :param style: String value of class attribute of node.
    :param layout: String value of layout definition to use
    :param template_root: Root path for template files, only required if the template_path config is relative.
    :param template: Template name to use for the content of this need
    :param pre_template: Template name to use for content added before need
    :param post_template: Template name to use for the content added after need
    """
    # location is used to provide source mapped warnings
    location = (docname, lineno) if docname else None

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
    tags = [v for v, _ in _split_list_with_dyn_funcs(tags, location)]
    if needs_config.tags and (
        unknown_tags := set(tags) - {t["name"] for t in needs_config.tags}
    ):
        raise InvalidNeedException(
            "invalid_tags", f"Tags {unknown_tags!r} not in 'needs_tags'."
        )

    # validate constraints
    constraints = [v for v, _ in _split_list_with_dyn_funcs(constraints, location)]
    if unknown_constraints := set(constraints) - set(needs_config.constraints):
        raise InvalidNeedException(
            "invalid_constraints",
            f"Constraints {unknown_constraints!r} not in 'needs_constraints'.",
        )

    # Add the need and all needed information
    needs_info: NeedsInfoType = {
        "docname": docname,
        "lineno": lineno,
        "lineno_content": lineno_content,
        "doctype": doctype,
        "content": content,
        "type": need_type,
        "type_name": need_type_data["title"],
        "type_prefix": need_type_data["prefix"],
        "type_color": need_type_data.get("color") or "#000000",
        "type_style": need_type_data.get("style") or "node",
        "status": status,
        "tags": tags,
        "constraints": constraints,
        "constraints_passed": True,
        "constraints_results": {},
        "id": need_id,
        "title": title,
        "collapse": collapse or False,
        "arch": arch or {},
        "style": style,
        "layout": layout,
        "template": template,
        "pre_template": pre_template,
        "post_template": post_template,
        "hide": hide,
        "jinja_content": jinja_content or False,
        "parts": parts or {},
        "is_part": False,
        "is_need": True,
        "id_parent": need_id,
        "id_complete": need_id,
        "is_external": is_external or False,
        "external_url": external_url if is_external else None,
        "external_css": external_css or "external_link",
        "is_modified": False,
        "modifications": 0,
        "has_dead_links": False,
        "has_forbidden_dead_links": False,
        "sections": sections or [],
        "section_name": sections[0] if sections else "",
        "signature": signature,
        "parent_need": "",
    }

    _add_extra_fields(needs_info, kwargs, needs_config)
    _add_link_fields(needs_info, kwargs, needs_config, location)
    _set_field_defaults(needs_info, needs_config)
    _copy_links(needs_info, needs_config)

    if parent_needs := needs_info.get("parent_needs"):
        # ensure parent_need is consistent with parent_needs
        needs_info["parent_need"] = parent_needs[0]

    if jinja_content:
        need_content_context = {**needs_info}
        need_content_context.update(**needs_config.filter_data)
        need_content_context.update(**needs_config.render_context)
        try:
            needs_info["content"] = jinja_parse(
                need_content_context, needs_info["content"]
            )
        except Exception as e:
            raise InvalidNeedException(
                "invalid_jinja_content",
                f"Error while rendering content: {e}",
            )

    if needs_info["template"]:
        needs_info["content"] = _prepare_template(
            needs_config, needs_info, "template", template_root
        )

    if needs_info["pre_template"]:
        needs_info["pre_content"] = _prepare_template(
            needs_config, needs_info, "pre_template", template_root
        )

    if needs_info["post_template"]:
        needs_info["post_content"] = _prepare_template(
            needs_config, needs_info, "post_template", template_root
        )

    return needs_info


def add_need(
    app: Sphinx,
    state: None | RSTState,
    docname: None | str,
    lineno: None | int,
    need_type: str,
    title: str,
    *,
    id: str | None = None,
    content: str | StringList = "",
    lineno_content: None | int = None,
    doctype: None | str = None,
    status: str | None = None,
    tags: None | str | list[str] = None,
    constraints: None | str | list[str] = None,
    parts: dict[str, NeedsPartType] | None = None,
    arch: dict[str, str] | None = None,
    signature: str = "",
    sections: list[str] | None = None,
    jinja_content: None | bool = False,
    hide: bool = False,
    collapse: None | bool = None,
    style: None | str = None,
    layout: None | str = None,
    template: None | str = None,
    pre_template: str | None = None,
    post_template: str | None = None,
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
    :param hide: boolean value.
    :param collapse: boolean value.
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

    if doctype is None and not is_external and docname:
        doctype = os.path.splitext(app.env.doc2path(docname))[1]

    needs_info = generate_need(
        needs_config=NeedsSphinxConfig(app.config),
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
    data: NeedsInfoType,
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
    data["arch"] = {}
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
                            data["arch"][key_name] = needuml["content"]
                            node_need_needumls_key_names.append(key_name)
                    else:
                        node_need_needumls_without_key.append(needuml)
                except KeyError:
                    pass

    # only store the first needuml-node which has no key option under diagram
    if node_need_needumls_without_key:
        data["arch"]["diagram"] = node_need_needumls_without_key[0]["content"]

    data["parts"] = {}
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
        state=None,
        docname=None,
        lineno=None,
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
    needs_info: NeedsInfoType,
    template_key: str,
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

    template_file_name = str(needs_info[template_key]) + ".need"
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


def _add_extra_fields(
    needs_info: NeedsInfoType, kwargs: dict[str, Any], config: NeedsSphinxConfig
) -> None:
    """Add extra option fields to the needs_info dictionary."""
    extra_keys = set(kwargs).difference(set(needs_info))
    for key in config.extra_options:
        if key in extra_keys:
            # TODO really we should not need to do this,
            # but the `add_extra_option` function does not guard against the keys clashing with existing internal fields,
            # this occurs in the core code with the github service adding `type` as an extra option

            # note we already warn if value not string in external/import code
            needs_info[key] = str(kwargs.get(key, ""))
        elif key not in needs_info:
            needs_info[key] = ""


def _add_link_fields(
    needs_info: NeedsInfoType,
    kwargs: dict[str, Any],
    config: NeedsSphinxConfig,
    location: tuple[str, int | None] | None,
) -> None:
    """Add extra link fields to the needs_info dictionary."""
    for link_type in config.extra_links:
        name = link_type["option"]
        # ensure the link type is in the needs_info dictionary,
        # and also ensure the back link is present
        needs_info[name] = []
        needs_info[f"{name}_back"] = []
        if name in kwargs:
            needs_info[name] = [
                v for v, _ in _split_list_with_dyn_funcs(kwargs[name], location)
            ]


def _copy_links(needs_info: NeedsInfoType, config: NeedsSphinxConfig) -> None:
    """Implement 'copy' logic for links."""
    copy_links: list[str] = []
    for link_type in config.extra_links:
        if link_type.get("copy", False) and (name := link_type["option"]) != "links":
            copy_links += needs_info[name]  # Save extra links for main-links
    needs_info["links"] += copy_links  # Set copied links to main-links


def _set_field_defaults(needs_info: NeedsInfoType, config: NeedsSphinxConfig) -> None:
    """Set default values."""
    # TODO should defaults be applied to external/import needs?
    # currently any "falsy" value will be replaced by the default, even if it was explicitly set
    for key, defaults in config.field_defaults.items():
        if key not in needs_info or needs_info[key]:
            continue
        for predicate, v in defaults.get("predicates", []):
            # use the first predicate that is satisfied
            if filter_single_need(needs_info, config, predicate):
                needs_info[key] = v
                break
        else:
            if "default" in defaults:
                needs_info[key] = defaults["default"]


def get_needs_view(app: Sphinx) -> NeedsView:
    """Return a read-only view of all resolved needs.

    .. important:: this should only be called within the write phase,
        after the needs have been fully collected.
        If not already done, this will ensure all needs are resolved
        (e.g. back links have been computed etc),
        and then lock the data to prevent further modification.
    """
    return SphinxNeedsData(app.env).get_needs_view()
