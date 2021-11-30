import hashlib
import os
import re
from typing import List, Union

from docutils import nodes
from docutils.statemachine import ViewList
from jinja2 import Template
from sphinx.util.nodes import nested_parse_with_titles

from sphinxcontrib.needs.api.configuration import NEEDS_CONFIG
from sphinxcontrib.needs.api.exceptions import (
    NeedsDuplicatedId,
    NeedsInvalidException,
    NeedsInvalidOption,
    NeedsNoIdException,
    NeedsStatusNotAllowed,
    NeedsTagNotAllowed,
    NeedsTemplateException,
)
from sphinxcontrib.needs.filter_common import filter_single_need
from sphinxcontrib.needs.logging import get_logger
from sphinxcontrib.needs.nodes import Need
from sphinxcontrib.needs.roles.need_part import find_parts, update_need_with_parts

logger = get_logger(__name__)


def add_need(
    app,
    state,
    docname,
    lineno,
    need_type,
    title,
    id=None,
    content="",
    status=None,
    tags=None,
    links_string=None,
    hide=False,
    hide_tags=False,
    hide_status=False,
    collapse=None,
    style=None,
    layout=None,
    template=None,
    pre_template=None,
    post_template=None,
    is_external=False,
    external_url=None,
    external_css="external_link",
    **kwargs,
):
    """
    Creates a new need and returns its node.

    ``add_need`` allows to create needs programmatically and use its returned node to be integrated in any
    docutils based structure.

    ``kwags`` can contain options defined in ``needs_extra_options`` and ``needs_extra_links``.
    If an entry is found in ``kwags``, which *is not* specified in the configuration or registered e.g. via
    ``add_extra_option``, an exception is raised.

    If ``is_external`` is set to ``True``, no node will be created.
    Instead the need is referencing an external url.
    Used mostly for :ref:`needs_external_needs` to integrate and reference needs from external documentation.

    **Usage**:

    Normally needs get created during handling of a specialised directive.
    So this pseudo-code shows how to use ``add_need`` inside such a directive.

    .. code-block:: python

        from docutils.parsers.rst import Directive
        from sphinxcontrib.needs.api import add_need

        class MyDirective(Directive)
            # configs and init routine

            def run():
                main_section = []

                docname = self.state.document.settings.env.docname

                # All needed sphinx-internal information we can take from our current directive class.
                # e..g app, state, lineno
                main_section += add_need(self.env.app, self.state, docname, self.lineno,
                                         need_type="req", title="my title", id="ID_001"
                                         content=self.content)

                # Feel free to add custom stuff to main_section like sections, text, ...

                return main_section

    :param app: Sphinx application object.
    :param state: Current state object.
    :param docname: documentation name.
    :param lineno: line number.
    :param need_type: Name of the need type to create.
    :param title: String as title.
    :param id: ID as string. If not given, a id will get generated.
    :param content: Content as single string.
    :param status: Status as string.
    :param tags: Tags as single string.
    :param links_string: Links as single string.
    :param hide: boolean value.
    :param hide_tags: boolean value. (Not used with Sphinx-Needs >0.5.0)
    :param hide_status: boolean value. (Not used with Sphinx-Needs >0.5.0)
    :param collapse: boolean value.
    :param style: String value of class attribute of node.
    :param layout: String value of layout definition to use
    :param template: Template name to use for the content of this need
    :param pre_template: Template name to use for content added before need
    :param post_template: Template name to use for the content added after need
    :param is_external: Is true, no node is created and need is referencing external url
    :param external_url: URL as string, which is used as target if ``is_external`` is ``True``
    :param external_css: CSS class name as string, which is set for the <a> tag.

    :return: node
    """
    #############################################################################################
    # Get environment
    #############################################################################################
    env = app.env
    types = env.app.config.needs_types
    type_name = ""
    type_prefix = ""
    type_color = ""
    type_style = ""
    found = False
    for ntype in types:
        if ntype["directive"] == need_type:
            type_name = ntype["title"]
            type_prefix = ntype["prefix"]
            type_color = ntype["color"] or "#000000"  # if no color set up user in config
            type_style = ntype["style"] or "node"  # if no style set up user in config
            found = True
            break
    if not found:
        # This should never happen. But it may happen, if Sphinx is called multiples times
        # inside one ongoing python process.
        # In this case the configuration from a prior sphinx run may be active, which has registered a directive,
        # which is reused inside a current document, but no type was defined for the current run...
        # Yeah, this really has happened...
        return [nodes.Text("", "")]

    # Get the id or generate a random string/hash string, which is hopefully unique
    # TODO: Check, if id was already given. If True, recalculate id
    # id = self.options.get("id", ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for
    # _ in range(5)))
    if id is None and env.app.config.needs_id_required:
        raise NeedsNoIdException(
            "An id is missing for this need and must be set, because 'needs_id_required' "
            "is set to True in conf.py. Need '{}' in {} ({})".format(title, docname, lineno)
        )

    if id is None:
        need_id = make_hashed_id(app, need_type, title, content)
    else:
        need_id = id

    if env.app.config.needs_id_regex and not re.match(env.app.config.needs_id_regex, need_id):
        raise NeedsInvalidException(
            "Given ID '{id}' does not match configured regex '{regex}'".format(
                id=need_id, regex=env.app.config.needs_id_regex
            )
        )

    # Calculate target id, to be able to set a link back
    if is_external:
        target_node = None
        external_url = external_url
    else:
        target_node = nodes.target("", "", ids=[need_id], refid=need_id)
        external_url = None

    # Handle status
    # Check if status is in needs_statuses. If not raise an error.
    if env.app.config.needs_statuses and status not in [stat["name"] for stat in env.app.config.needs_statuses]:
        raise NeedsStatusNotAllowed(
            f"Status {status} of need id {need_id} is not allowed " "by config value 'needs_statuses'."
        )

    if tags is None:
        tags = []
    if len(tags) > 0:

        # tags should be a string, but it can also be already a list,which can be used.
        if isinstance(tags, str):
            tags = [tag.strip() for tag in re.split(";|,", tags)]
        new_tags = []  # Shall contain only valid tags
        for i in range(len(tags)):
            if len(tags[i]) == 0 or tags[i].isspace():
                logger.warning(f"Scruffy tag definition found in need {need_id}. " "Defined tag contains spaces only.")
            else:
                new_tags.append(tags[i])

        tags = new_tags
        # Check if tag is in needs_tags. If not raise an error.
        if env.app.config.needs_tags:
            for tag in tags:
                if tag not in [tag["name"] for tag in env.app.config.needs_tags]:
                    raise NeedsTagNotAllowed(
                        f"Tag {tag} of need id {need_id} is not allowed " "by config value 'needs_tags'."
                    )
        # This may have cut also dynamic function strings, as they can contain , as well.
        # So let put them together again
        # ToDo: There may be a smart regex for the splitting. This would avoid this mess of code...
    tags = _fix_list_dyn_func(tags)

    #############################################################################################
    # Add need to global need list
    #############################################################################################
    # be sure, global var is available. If not, create it
    if not hasattr(env, "needs_all_needs"):
        env.needs_all_needs = {}

    if need_id in env.needs_all_needs:
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
    max_length = env.app.config.needs_max_title_length
    if max_length == -1 or len(title) <= max_length:
        trimmed_title = title
    elif max_length <= 3:
        trimmed_title = title[:max_length]
    else:
        trimmed_title = title[: max_length - 3] + "..."

    # Add the need and all needed information
    needs_info = {
        "docname": docname,
        "lineno": lineno,
        "target_node": target_node,
        "external_url": external_url,
        "content_node": None,  # gets set after rst parsing
        "type": need_type,
        "type_name": type_name,
        "type_prefix": type_prefix,
        "type_color": type_color,
        "type_style": type_style,
        "status": status,
        "tags": tags,
        "id": need_id,
        "title": trimmed_title,
        "full_title": title,
        "content": content,
        "collapse": collapse,
        "style": style,
        "layout": layout,
        "template": template,
        "pre_template": pre_template,
        "post_template": post_template,
        "hide": hide,
        "parts": {},
        "is_part": False,
        "is_need": True,
        "parent_need": None,
        "is_external": is_external or False,
        "external_css": external_css or "external_link",
        "is_modified": False,  # needed by needextend
        "modifications": 0,  # needed by needextend
    }
    # needs_extra_options = env.config.needs_extra_options.keys()
    needs_extra_option_names = NEEDS_CONFIG.get("extra_options").keys()
    _merge_extra_options(needs_info, kwargs, needs_extra_option_names)

    needs_global_options = env.config.needs_global_options
    _merge_global_options(app, needs_info, needs_global_options)

    link_names = [x["option"] for x in env.config.needs_extra_links]
    for keyword in kwargs:
        if keyword not in needs_extra_option_names and keyword not in link_names:
            raise NeedsInvalidOption(
                "Unknown Option {}. "
                "Use needs_extra_options or needs_extra_links in conf.py"
                "to define this option.".format(keyword)
            )

    # Merge links
    copy_links = []

    for link_type in env.config.needs_extra_links:
        # Check, if specific link-type got some arguments during method call
        if link_type["option"] not in kwargs and link_type["option"] not in needs_global_options:
            # if not we set no links, but entry in needS_info must be there
            links = []
        elif link_type["option"] in needs_global_options and (
            link_type["option"] not in kwargs or len(str(kwargs[link_type["option"]])) == 0
        ):
            # If it is in global option, value got already set during prior handling of them
            links_string = needs_info[link_type["option"]]
            links = _read_in_links(links_string)
        else:
            # if it is set in kwargs, take this value and maybe override set value from global_options
            links_string = kwargs[link_type["option"]]
            links = _read_in_links(links_string)

        needs_info[link_type["option"]] = links
        needs_info["{}_back".format(link_type["option"])] = []

        if "copy" not in link_type:
            link_type["copy"] = False

        if link_type["copy"] and link_type["option"] != "links":
            copy_links += links  # Save extra links for main-links

    needs_info["links"] += copy_links  # Set copied links to main-links

    env.needs_all_needs[need_id] = needs_info

    # Template builds
    ##############################

    # template
    if needs_info["template"]:
        new_content = _prepare_template(app, needs_info, "template")
        # Overwrite current content
        content = new_content
        needs_info["content"] = new_content

    # pre_template
    if needs_info["pre_template"]:
        pre_content = _prepare_template(app, needs_info, "pre_template")
        needs_info["pre_content"] = pre_content
    else:
        pre_content = None

    # post_template
    if needs_info["post_template"]:
        post_content = _prepare_template(app, needs_info, "post_template")
        needs_info["post_content"] = post_content
    else:
        post_content = None

    if needs_info["is_external"]:
        return []

    if needs_info["hide"]:
        return [target_node]

    # Adding of basic Need node.
    ############################
    # Title and meta data information gets added alter during event handling via process_need_nodes()
    # We just add a basic need node and render the rst-based content, because this can not be done later.
    # style_classes = ['need', type_name, 'need-{}'.format(type_name.lower())]  # Used < 0.4.4
    style_classes = ["need", f"need-{need_type.lower()}"]
    if style:
        style_classes.append(style)

    node_need = Need("", classes=style_classes, ids=[need_id], refid=need_id)

    # Render rst-based content and add it to the need-node

    node_need_content = _render_template(content, docname, lineno, state)
    need_parts = find_parts(node_need_content)
    update_need_with_parts(env, needs_info, need_parts)

    node_need += node_need_content.children

    needs_info["content_node"] = node_need

    return_nodes = [target_node] + [node_need]
    if pre_content:
        node_need_pre_content = _render_template(pre_content, docname, lineno, state)
        pre_container = nodes.container()
        pre_container += node_need_pre_content.children
        return_nodes = node_need_pre_content.children + return_nodes

    if post_content:
        node_need_post_content = _render_template(post_content, docname, lineno, state)
        post_container = nodes.container()
        post_container += node_need_post_content.children
        return_nodes = return_nodes + node_need_post_content.children

    return return_nodes


def del_need(app, id):
    """
    Deletes an existing need.

    :param app: Sphinx application object.
    :param id: Sphinx need id.
    """
    if id in app.env.needs_all_needs:
        del app.env.needs_all_needs[id]
    else:
        logger.warning(f"Given need id {id} not exists!")


def add_external_need(
    app,
    need_type,
    title,
    id=None,
    external_url=None,
    external_css="external_link",
    content="",
    status=None,
    tags=None,
    links_string=None,
    **kwargs,
):
    """
    Adds an external need from an external source.
    This need does not have any representation in the current documentation project.
    However, it can be linked and filtered.
    It's reference will open a link to another, external  sphinx documentation project.

    It return an empty list (without any nodes), so no nodes will be added to the document.

    :param app: Sphinx application object.
    :param need_type: Name of the need type to create.
    :param title: String as title.
    :param id: ID as string. If not given, a id will get generated.
    :param external_url: URL as string, which shall be used as link to the original need source
    :param content: Content as single string.
    :param status: Status as string.
    :param tags: Tags as single string.
    :param links_string: Links as single string.
    :param external_css: CSS class name as string, which is set for the <a> tag.
    :param kwargs:

    :return: Empty list
    """

    kwargs["state"] = None
    kwargs["docname"] = None
    kwargs["lineno"] = None
    kwargs["need_type"] = need_type
    kwargs["id"] = id
    kwargs["content"] = content
    kwargs["title"] = title
    kwargs["status"] = status
    kwargs["tags"] = tags
    kwargs["links_string"] = links_string
    kwargs["is_external"] = True
    kwargs["external_url"] = external_url
    kwargs["external_css"] = external_css

    return add_need(app=app, **kwargs)


def _prepare_template(app, needs_info, template_key):
    template_folder = app.config.needs_template_folder
    if not os.path.isabs(template_folder):
        template_folder = os.path.join(app.confdir, template_folder)

    if not os.path.isdir(template_folder):
        raise NeedsTemplateException(f"Template folder does not exist: {template_folder}")

    template_file_name = needs_info[template_key] + ".need"
    template_path = os.path.join(template_folder, template_file_name)
    if not os.path.isfile(template_path):
        raise NeedsTemplateException(f"Template does not exist: {template_path}")

    with open(template_path) as template_file:
        template_content = "".join(template_file.readlines())
    template_obj = Template(template_content)
    new_content = template_obj.render(**needs_info)

    return new_content


def _render_template(content, docname, lineno, state):
    rst = ViewList()
    for line in content.split("\n"):
        rst.append(line, docname, lineno)
    node_need_content = nodes.Element()
    node_need_content.document = state.document
    nested_parse_with_titles(state, rst, node_need_content)
    return node_need_content


def _read_in_links(links_string: Union[str, List[str]]):
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
                logger.warning(f"Grubby link definition found in need {id}. " "Defined link contains spaces only.")
            else:
                links.append(link.strip())

        # This may have cut also dynamic function strings, as they can contain , as well.
        # So let put them together again
        # ToDo: There may be a smart regex for the splitting. This would avoid this mess of code...
    return _fix_list_dyn_func(links)


def make_hashed_id(app, need_type, full_title, content, id_length=None):
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
    types = app.config.needs_types
    if id_length is None:
        id_length = app.config.needs_id_length
    type_prefix = None
    for ntype in types:
        if ntype["directive"] == need_type:
            type_prefix = ntype["prefix"]
            break
    if type_prefix is None:
        raise NeedsInvalidException(f"Given need_type {need_type} is unknown. File {app.env.docname}")

    hashable_content = full_title or "\n".join(content)
    return "{}{}".format(type_prefix, hashlib.sha1(hashable_content.encode("UTF-8")).hexdigest().upper()[:id_length])


def _fix_list_dyn_func(list):
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


def _merge_extra_options(needs_info, needs_kwargs, needs_extra_options):
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


def _merge_global_options(app, needs_info, global_options):
    """Add all global defined options to needs_info"""
    if global_options is None:
        return
    for key, value in global_options.items():

        # If key already exists in needs_info, this global_option got overwritten manually in current need
        if key in needs_info and needs_info[key]:
            continue

        if isinstance(value, tuple):
            values = [value]
        elif isinstance(value, list):
            values = value
        else:
            needs_info[key] = value
            continue

        for single_value in values:
            if len(single_value) < 2 or len(single_value) > 3:
                raise NeedsInvalidException(f"global option tuple has wrong amount of parameters: {key}")
            if filter_single_need(app, needs_info, single_value[1]):
                # Set value, if filter has matched
                needs_info[key] = single_value[0]
            elif len(single_value) == 3 and (key not in needs_info.keys() or len(str(needs_info[key])) > 0):
                # Otherwise set default, but only if no value was set before or value is "" and a default is defined
                needs_info[key] = single_value[2]
            else:
                # If not value was set until now, we have to set an empty value, so that we are sure that each need
                # has at least the key.
                if key not in needs_info.keys():
                    needs_info[key] = ""
