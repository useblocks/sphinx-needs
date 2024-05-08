from __future__ import annotations

import hashlib
import os
import re
from contextlib import contextmanager
from typing import Any, Iterator

from docutils import nodes
from docutils.parsers.rst.states import RSTState
from docutils.statemachine import StringList
from jinja2 import Template
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.api.configuration import NEEDS_CONFIG
from sphinx_needs.api.exceptions import (
    NeedsConstraintNotAllowed,
    NeedsDuplicatedId,
    NeedsInvalidException,
    NeedsInvalidOption,
    NeedsNoIdException,
    NeedsStatusNotAllowed,
    NeedsTagNotAllowed,
    NeedsTemplateException,
)
from sphinx_needs.config import GlobalOptionsType, NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.directives.needuml import Needuml, NeedumlException
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.logging import get_logger
from sphinx_needs.nodes import Need
from sphinx_needs.roles.need_part import find_parts, update_need_with_parts
from sphinx_needs.utils import jinja_parse

logger = get_logger(__name__)


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
    status: str | None = None,
    tags: None | str | list[str] = None,
    constraints: None | str | list[str] = None,
    constraints_passed: None | bool = None,
    links_string: None | str | list[str] = None,
    delete: bool = False,
    jinja_content: bool = False,
    hide: bool = False,
    hide_tags: bool = False,
    hide_status: bool = False,
    collapse: None | bool = None,
    style: None | str = None,
    layout: None | str = None,
    template: None | str = None,
    pre_template: str | None = None,
    post_template: str | None = None,
    is_external: bool = False,
    external_url: str | None = None,
    external_css: str = "external_link",
    **kwargs: Any,
) -> list[nodes.Node]:
    """
    Creates a new need and returns its node.

    ``add_need`` allows to create needs programmatically and use its returned node to be integrated in any
    docutils based structure.

    ``kwags`` can contain options defined in ``needs_extra_options`` and ``needs_extra_links``.
    If an entry is found in ``kwags``, which *is not* specified in the configuration or registered e.g. via
    ``add_extra_option``, an exception is raised.

    If ``is_external`` is set to ``True``, no node will be created.
    Instead, the need is referencing an external url.
    Used mostly for :ref:`needs_external_needs` to integrate and reference needs from external documentation.

    **Usage**:

    Normally needs get created during handling of a specialised directive.
    So this pseudocode shows how to use ``add_need`` inside such a directive.

    .. code-block:: python

        from sphinx.util.docutils import SphinxDirective
        from sphinx_needs.api import add_need

        class MyDirective(SphinxDirective)
            # configs and init routine

            def run():
                main_section = []

                docname = self.env.docname

                # All needed sphinx-internal information we can take from our current directive class.
                # e..g app, state, lineno
                main_section += add_need(self.env.app, self.state, docname, self.lineno,
                                         need_type="req", title="my title", id="ID_001"
                                         content=self.content)

                # Feel free to add custom stuff to main_section like sections, text, ...

                return main_section

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
    :param id: ID as string. If not given, an id will get generated.
    :param content: Content of the need, either as a ``str``
        or a ``StringList`` (a string with mapping to the source text).
    :param status: Status as string.
    :param tags: Tags as single string.
    :param constraints: Constraints as single, comma separated, string.
    :param constraints_passed: Contains bool describing if all constraints have passed
    :param links_string: Links as single string. (Not used)
    :param delete: boolean value (Remove the complete need).
    :param hide: boolean value.
    :param hide_tags: boolean value. (Not used with Sphinx-Needs >0.5.0)
    :param hide_status: boolean value. (Not used with Sphinx-Needs >0.5.0)
    :param collapse: boolean value.
    :param style: String value of class attribute of node.
    :param layout: String value of layout definition to use
    :param template: Template name to use for the content of this need
    :param pre_template: Template name to use for content added before need
    :param post_template: Template name to use for the content added after need

    :return: node
    """
    #############################################################################################
    # Get environment
    #############################################################################################
    env = app.env
    needs_config = NeedsSphinxConfig(app.config)
    types = needs_config.types
    type_name = ""
    type_prefix = ""
    type_color = ""
    type_style = ""
    found = False

    # Log messages for need elements that could not be imported.
    configured_need_types = [ntype["directive"] for ntype in types]
    if need_type not in configured_need_types:
        logger.warning(
            f"Couldn't create need {id}. Reason: The need-type (i.e. `{need_type}`) is not set "
            "in the project's 'need_types' configuration in conf.py. [needs.add]",
            type="needs",
            subtype="add",
            location=(docname, lineno) if docname else None,
        )

    for ntype in types:
        if ntype["directive"] == need_type:
            type_name = ntype["title"]
            type_prefix = ntype["prefix"]
            type_color = (
                ntype["color"] or "#000000"
            )  # if no color set up user in config
            type_style = ntype["style"] or "node"  # if no style set up user in config
            found = True
            break

    if delete:
        # Don't generate a need object if the :delete: option is enabled.
        return [nodes.Text("")]
    if not found:
        # This should never happen. But it may happen, if Sphinx is called multiples times
        # inside one ongoing python process.
        # In this case the configuration from a prior sphinx run may be active, which has registered a directive,
        # which is reused inside a current document, but no type was defined for the current run...
        # Yeah, this really has happened...
        return [nodes.Text("")]

    # Get the id or generate a random string/hash string, which is hopefully unique
    # TODO: Check, if id was already given. If True, recalculate id
    # id = self.options.get("id", ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for
    # _ in range(5)))
    if id is None and needs_config.id_required:
        raise NeedsNoIdException(
            "An id is missing for this need and must be set, because 'needs_id_required' "
            f"is set to True in conf.py. Need '{title}' in {docname} ({lineno})"
        )

    if id is None:
        need_id = make_hashed_id(
            app,
            need_type,
            title,
            "\n".join(content) if isinstance(content, StringList) else content,
        )
    else:
        need_id = id

    if (
        needs_config.id_regex
        and not is_external
        and not re.match(needs_config.id_regex, need_id)
    ):
        raise NeedsInvalidException(
            f"Given ID '{need_id}' does not match configured regex '{needs_config.id_regex}'"
        )

    # Handle status
    # Check if status is in needs_statuses. If not raise an error.
    if needs_config.statuses and status not in [
        stat["name"] for stat in needs_config.statuses
    ]:
        raise NeedsStatusNotAllowed(
            f"Status {status} of need id {need_id} is not allowed "
            "by config value 'needs_statuses'."
        )

    if tags is None:
        tags = []
    if len(tags) > 0:
        # tags should be a string, but it can also be already a list, which can be used.
        if isinstance(tags, str):
            tags = [tag.strip() for tag in re.split("[;,]", tags)]
        new_tags = []  # Shall contain only valid tags
        for i in range(len(tags)):
            if len(tags[i]) == 0 or tags[i].isspace():
                logger.warning(
                    f"Scruffy tag definition found in need {need_id!r}. "
                    "Defined tag contains spaces only. [needs.add]",
                    type="needs",
                    subtype="add",
                    location=(docname, lineno) if docname else None,
                )
            else:
                new_tags.append(tags[i])

        tags = new_tags
        # Check if tag is in needs_tags. If not raise an error.
        if needs_config.tags:
            for tag in tags:
                needs_tags = [tag["name"] for tag in needs_config.tags]
                if tag not in needs_tags:
                    raise NeedsTagNotAllowed(
                        f"Tag {tag} of need id {need_id} is not allowed "
                        "by config value 'needs_tags'."
                    )
        # This may have cut also dynamic function strings, as they can contain , as well.
        # So let put them together again
        # ToDo: There may be a smart regex for the splitting. This would avoid this mess of code...
    else:
        tags = []
    tags = _fix_list_dyn_func(tags)

    if constraints is None:
        constraints = []
    if len(constraints) > 0:
        # tags should be a string, but it can also be already a list,which can be used.
        if isinstance(constraints, str):
            constraints = [
                constraint.strip() for constraint in re.split("[;,]", constraints)
            ]

        new_constraints = []  # Shall contain only valid constraints
        for i in range(len(constraints)):
            if len(constraints[i]) == 0 or constraints[i].isspace():
                logger.warning(
                    f"Scruffy constraint definition found in need {need_id!r}. "
                    "Defined constraint contains spaces only. [needs.add]",
                    type="needs",
                    subtype="add",
                    location=(docname, lineno) if docname else None,
                )
            else:
                new_constraints.append(constraints[i])

        constraints = new_constraints
        # Check if constraint is in needs_constraints. If not raise an error.
        if needs_config.constraints:
            for constraint in constraints:
                if constraint not in needs_config.constraints.keys():
                    raise NeedsConstraintNotAllowed(
                        f"Constraint {constraint} of need id {need_id} is not allowed "
                        "by config value 'needs_constraints'."
                    )
        # This may have cut also dynamic function strings, as they can contain , as well.
        # So let put them together again
        # ToDo: There may be a smart regex for the splitting. This would avoid this mess of code...
    else:
        constraints = []
    constraints = _fix_list_dyn_func(constraints)

    #############################################################################################
    # Add need to global need list
    #############################################################################################

    if need_id in SphinxNeedsData(env).get_or_create_needs():
        if id:
            raise NeedsDuplicatedId(
                f"A need with ID {need_id} already exists! "
                f"This is not allowed. Document {docname}[{lineno}] Title: {title}."
            )
        else:  # this is a generated ID
            raise NeedsDuplicatedId(
                "Needs could not generate a unique ID for a need with "
                "the title '{}' because another need had the same title. "
                "Either supply IDs for the requirements or ensure the "
                "titles are different.  NOTE: If title is being generated "
                "from the content, then ensure the first sentence of the "
                "requirements are different.".format(" ".join(title))
            )

    # Trim title if it is too long
    max_length = needs_config.max_title_length
    if max_length == -1 or len(title) <= max_length:
        trimmed_title = title
    elif max_length <= 3:
        trimmed_title = title[:max_length]
    else:
        trimmed_title = title[: max_length - 3] + "..."

    # Calculate doc type, e.g. .rst or .md
    doctype = os.path.splitext(env.doc2path(docname))[1] if docname else ""

    # Add the need and all needed information
    needs_info: NeedsInfoType = {
        "docname": docname,
        "lineno": lineno,
        "lineno_content": lineno_content,
        "doctype": doctype,
        "target_id": need_id,
        "content": "\n".join(content) if isinstance(content, StringList) else content,
        "content_node": None,
        "content_id": None,
        "type": need_type,
        "type_name": type_name,
        "type_prefix": type_prefix,
        "type_color": type_color,
        "type_style": type_style,
        "status": status,
        "tags": tags,
        "constraints": constraints,
        "constraints_passed": None,
        "constraints_results": {},
        "id": need_id,
        "title": trimmed_title,
        "full_title": title,
        "collapse": collapse,
        "arch": {},  # extracted later
        "style": style,
        "layout": layout,
        "template": template,
        "pre_template": pre_template,
        "post_template": post_template,
        "hide": hide,
        "delete": delete,
        "jinja_content": jinja_content,
        "parts": {},
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
        "sections": [],
        "section_name": "",
        "signature": "",
        "parent_need": "",
    }
    needs_extra_option_names = list(NEEDS_CONFIG.extra_options)
    _merge_extra_options(needs_info, kwargs, needs_extra_option_names)

    needs_global_options = needs_config.global_options
    _merge_global_options(app, needs_info, needs_global_options)

    link_names = [x["option"] for x in needs_config.extra_links]
    for keyword in kwargs:
        if keyword not in needs_extra_option_names and keyword not in link_names:
            raise NeedsInvalidOption(
                f"Unknown Option {keyword}. "
                "Use needs_extra_options or needs_extra_links in conf.py"
                "to define this option."
            )

    # Merge links
    copy_links = []

    for link_type in needs_config.extra_links:
        # Check, if specific link-type got some arguments during method call
        if (
            link_type["option"] not in kwargs
            and link_type["option"] not in needs_global_options
        ):
            # if not we set no links, but entry in needS_info must be there
            links = []
        elif link_type["option"] in needs_global_options and (
            link_type["option"] not in kwargs
            or len(str(kwargs[link_type["option"]])) == 0
        ):
            # If it is in global option, value got already set during prior handling of them
            links = _read_in_links(needs_info[link_type["option"]])
        else:
            # if it is set in kwargs, take this value and maybe override set value from global_options
            links = _read_in_links(kwargs[link_type["option"]])

        needs_info[link_type["option"]] = links
        needs_info["{}_back".format(link_type["option"])] = []

        if "copy" not in link_type:
            link_type["copy"] = False

        if link_type["copy"] and link_type["option"] != "links":
            copy_links += links  # Save extra links for main-links

    needs_info["links"] += copy_links  # Set copied links to main-links

    if jinja_content:
        need_content_context = {**needs_info}
        need_content_context.update(**needs_config.filter_data)
        need_content_context.update(**needs_config.render_context)
        needs_info["content"] = content = jinja_parse(
            need_content_context, needs_info["content"]
        )

    if needs_info["template"]:
        needs_info["content"] = content = _prepare_template(app, needs_info, "template")

    if needs_info["pre_template"]:
        needs_info["pre_content"] = _prepare_template(app, needs_info, "pre_template")

    if needs_info["post_template"]:
        needs_info["post_content"] = _prepare_template(app, needs_info, "post_template")

    SphinxNeedsData(env).get_or_create_needs()[need_id] = needs_info

    if needs_info["is_external"]:
        return []

    assert state is not None, "parser state must be set if need is not external"

    return _create_need_node(needs_info, env, state, content)


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

    need_parts = find_parts(node_need)
    update_need_with_parts(env, data, need_parts)

    data["content_id"] = node_need["ids"][0]

    # Create a copy of the content
    data["content_node"] = node_need.deepcopy()

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
    env = app.env
    needs = SphinxNeedsData(env).get_or_create_needs()
    if need_id in needs:
        del needs[need_id]
    else:
        logger.warning(f"Given need id {need_id} not exists! [needs]", type="needs")


def add_external_need(
    app: Sphinx,
    need_type: str,
    title: str | None = None,
    id: str | None = None,
    external_url: str | None = None,
    external_css: str = "external_link",
    content: str = "",
    status: str | None = None,
    tags: str | None = None,
    constraints: str | None = None,
    links_string: str | None = None,
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
    :param tags: Tags as single string.
    :param constraints: constraints as single, comma separated string.
    :param links_string: Links as single string.
    :param external_css: CSS class name as string, which is set for the <a> tag.

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
        links_string=links_string,
        is_external=True,
        external_url=external_url,
        external_css=external_css,
        **kwargs,
    )


def _prepare_template(app: Sphinx, needs_info: NeedsInfoType, template_key: str) -> str:
    needs_config = NeedsSphinxConfig(app.config)
    template_folder = needs_config.template_folder
    if not os.path.isabs(template_folder):
        template_folder = os.path.join(app.srcdir, template_folder)

    if not os.path.isdir(template_folder):
        raise NeedsTemplateException(
            f"Template folder does not exist: {template_folder}"
        )

    template_file_name = needs_info[template_key] + ".need"
    template_path = os.path.join(template_folder, template_file_name)
    if not os.path.isfile(template_path):
        raise NeedsTemplateException(f"Template does not exist: {template_path}")

    with open(template_path) as template_file:
        template_content = "".join(template_file.readlines())
    template_obj = Template(template_content)
    new_content = template_obj.render(**needs_info, **needs_config.render_context)

    return new_content


def _read_in_links(links_string: None | str | list[str]) -> list[str]:
    # Get links
    links = []
    if links_string:
        # Check if links_string is really a string, otherwise it will be a list, which can be used
        # without modifications
        if isinstance(links_string, str):
            link_list = re.split(";|,", links_string)
        else:
            link_list = links_string
        for link in link_list:
            if link.isspace():
                logger.warning(
                    f"Grubby link definition found in need {id}. "
                    "Defined link contains spaces only. [needs]",
                    type="needs",
                )
            else:
                links.append(link.strip())

        # This may have cut also dynamic function strings, as they can contain , as well.
        # So let put them together again
        # ToDo: There may be a smart regex for the splitting. This would avoid this mess of code...
    return _fix_list_dyn_func(links)


def make_hashed_id(
    app: Sphinx,
    need_type: str,
    full_title: str,
    content: str,
    id_length: int | None = None,
) -> str:
    """
    Creates an ID based on title or need.

    Also cares about the correct prefix, which is specified for each need type.

    :param app: Sphinx application object
    :param need_type: name of the need directive, e.g. req
    :param full_title: full title of the need
    :param content: content of the need
    :param id_length: maximum length of the generated ID
    :return: ID as string
    """
    needs_config = NeedsSphinxConfig(app.config)
    types = needs_config.types
    if id_length is None:
        id_length = needs_config.id_length
    type_prefix = None
    for ntype in types:
        if ntype["directive"] == need_type:
            type_prefix = ntype["prefix"]
            break
    if type_prefix is None:
        raise NeedsInvalidException(
            f"Given need_type {need_type} is unknown. File {app.env.docname}"
        )

    hashable_content = full_title or "\n".join(content)
    hashed_id = hashlib.sha1(hashable_content.encode("UTF-8")).hexdigest().upper()

    # check if needs_id_from_title is configured
    cal_hashed_id = hashed_id
    if needs_config.id_from_title:
        id_from_title = full_title.upper().replace(" ", "_") + "_"
        cal_hashed_id = id_from_title + hashed_id

    return f"{type_prefix}{cal_hashed_id[:id_length]}"


def _fix_list_dyn_func(list: list[str]) -> list[str]:
    """
    This searches a list for dynamic function fragments, which may have been cut by generic searches for ",|;".

    Example:
    `link_a, [[copy('links', need_id)]]` this will be splitted in list of 3 parts:

    #. link_a
    #. [[copy('links'
    #. need_id)]]

    This function fixes the above list to the following:

    #. link_a
    #. [[copy('links', need_id)]]

    :param list: list which may contain splitted function calls
    :return: list of fixed elements
    """
    open_func_string = False
    new_list = []
    for element in list:
        # If dyn_func got not cut, just add it
        if "[[" in element and "]]" in element:
            new_list.append(element)
        # Other check if this is the starting element of dyn function
        elif "[[" in element:
            open_func_string = True
            new_link = [element]
        # Check if this is the ending element if dyn function
        elif "]]" in element:
            new_link.append(element)
            open_func_string = False
            element = ",".join(new_link)
            new_list.append(element)
        # Check it is a "middle" part of the dyn function
        elif open_func_string:
            new_link.append(element)
        # Looks like it isn't a cut dyn_func, just add.
        else:
            new_list.append(element)
    return new_list


def _merge_extra_options(
    needs_info: NeedsInfoType,
    needs_kwargs: dict[str, Any],
    needs_extra_options: list[str],
) -> set[str]:
    """Add any extra options introduced via options_ext to needs_info"""
    extra_keys = set(needs_kwargs.keys()).difference(set(needs_info.keys()))

    for key in needs_extra_options:
        if key in extra_keys:
            needs_info[key] = str(needs_kwargs[key])
        elif key not in needs_info.keys():
            # Finally add all not used extra options with empty value to need_info.
            # Needed for filters, which need to access these empty/not used options.
            needs_info[key] = ""

    return extra_keys


def _merge_global_options(
    app: Sphinx, needs_info: NeedsInfoType, global_options: GlobalOptionsType
) -> None:
    """Add all global defined options to needs_info"""
    if global_options is None:
        return
    config = NeedsSphinxConfig(app.config)
    for key, value in global_options.items():
        # If key already exists in needs_info, this global_option got overwritten manually in current need
        if needs_info.get(key):
            continue

        if isinstance(value, tuple):
            values = [value]
        elif isinstance(value, list):
            values = value
        else:
            needs_info[key] = value
            continue

        for single_value in values:
            # TODO should first match break loop?
            if len(single_value) < 2 or len(single_value) > 3:
                # TODO this should be validated earlier at the "config" level
                raise NeedsInvalidException(
                    f"global option tuple has wrong amount of parameters: {key}"
                )
            if filter_single_need(needs_info, config, single_value[1]):
                # Set value, if filter has matched
                needs_info[key] = single_value[0]
            elif len(single_value) == 3 and (
                key not in needs_info.keys() or len(str(needs_info[key])) > 0
            ):
                # Otherwise set default, but only if no value was set before or value is "" and a default is defined
                needs_info[key] = single_value[2]
            else:
                # If not value was set until now, we have to set an empty value, so that we are sure that each need
                # has at least the key.
                if key not in needs_info.keys():
                    needs_info[key] = ""
