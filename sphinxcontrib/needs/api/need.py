import hashlib
import os
import re
from typing import List, Optional

from docutils import nodes
from docutils.nodes import Node
from docutils.statemachine import ViewList
from jinja2 import Template
from sphinx.application import Sphinx
from sphinx.util.nodes import nested_parse_with_titles

import sphinxcontrib.needs.directives.need
from sphinxcontrib.needs import utils
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
from sphinxcontrib.needs.roles.need_part import find_parts, update_need_with_parts

logger = get_logger(__name__)


class NeedType:
    def __init__(self, directive: str, name: str, prefix: str, color, style):
        self.directive = directive
        self.name = name
        self.prefix = prefix
        self.color = color
        self.style = style


def add_need(
    app: Sphinx,
    state,
    docname,
    lineno: int,
    need_type: str,
    title: str,
    id: Optional[str] = None,
    content="",
    status=None,
    tags: Optional[str] = None,
    links_string: Optional[str] = None,
    hide=False,
    hide_tags=False,
    hide_status=False,
    collapse=None,
    style=None,
    layout=None,
    template=None,
    pre_template=None,
    post_template=None,
    **kwargs
) -> List[Node]:
    """
    Creates a new need and returns its node.

    ``add_need`` allows to create needs programmatically and use its returned node to
    be integrated in any docutils based structure.

    ``kwargs`` can contain options defined in ``needs_extra_options`` and
    ``needs_extra_links``. If an entry is found in ``kwargs``, which *is not* specified
    in the configuration or registered e.g. via ``add_extra_option``, an exception is
    raised.

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

                # All needed sphinx-internal information we can take from our current
                # directive class. e.g app, state, lineno
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

    :return: list[Node]
    """
    ####################################################################################
    # Get environment
    ####################################################################################
    env = app.env
    config = app.config

    type_info = next(
        (t for t in config.needs_types if t["directive"] == need_type), None
    )

    if type_info is None:
        # This should never happen. But it may happen, if Sphinx is called multiples
        # times inside one ongoing python process. In this case the configuration from
        # a prior sphinx run may be active, which has registered a directive, which is
        # reused inside a current document, but no type was defined for the current run.
        # Yeah, this really has happened...
        return [nodes.Text("", "")]

    need_type_info = NeedType(
        directive=need_type,
        name=type_info["title"],
        prefix=type_info["prefix"],
        color=type_info["color"],
        style=type_info["style"],
    )

    # Get the id or generate a random string/hash string, which is hopefully unique
    # TODO: Check, if id was already given. If True, recalculate id
    # id = self.options.get(
    #   "id",
    #   ''.join(
    #       random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(5)
    #   )
    # )
    if id is None and config.needs_id_required:
        raise NeedsNoIdException(
            "An id is missing for this need and must be set, because 'needs_id_required' "
            "is set to True in conf.py. Need '{}' in {} ({})".format(
                title, docname, lineno
            )
        )

    need_id = id or make_hashed_id(need_type_info.prefix, title or content)

    if config.needs_id_regex and not re.match(config.needs_id_regex, need_id):
        raise NeedsInvalidException(
            "Given ID '{id}' does not match configured regex '{regex}'".format(
                id=need_id, regex=config.needs_id_regex
            )
        )

    # Calculate target id, to be able to set a link back
    target_node = nodes.target('', '', ids=[need_id],  refid=need_id)

    # Handle status
    # Check if status is in needs_statuses. If not raise an error.
    allowed_status_names = (s["name"] for s in config.needs_statuses)
    if config.needs_statuses and status not in allowed_status_names:
        raise NeedsStatusNotAllowed(
            "Status {0} of need id {1} is not allowed "
            "by config value 'needs_statuses'.".format(status, need_id)
        )

    allowed_tags = None
    if config.needs_tags:
        allowed_tags = [tag["name"] for tag in config.needs_tags]

    tag_list = _split_tags(tags, need_id, allowed_tags)

    ####################################################################################
    # Add need to global need list
    ####################################################################################
    # be sure, global var is available. If not, create it
    if not hasattr(env, "needs_all_needs"):
        env.needs_all_needs = {}

    if need_id in env.needs_all_needs.keys():
        if id:
            raise NeedsDuplicatedId(
                "A need with ID {} already exists! "
                "This is not allowed. Document {}[{}] Title: {}.".format(
                    need_id, docname, lineno, title
                )
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
    trimmed_title = utils.trim_title(title, max_length)

    # Add the need and all needed information
    needs_info = {
        "docname": docname,
        "lineno": lineno,
        "target_node": target_node,
        "content_node": None,  # gets set after rst parsing
        "type": need_type_info.directive,
        "type_name": need_type_info.name,
        "type_prefix": need_type_info.prefix,
        "type_color": need_type_info.color,
        "type_style": need_type_info.style,
        "status": status,
        "tags": tag_list,
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
    }
    needs_extra_options = config.needs_extra_options.keys()
    _merge_extra_options(needs_info, kwargs, needs_extra_options)

    needs_global_options = config.needs_global_options
    _merge_global_options(needs_info, needs_global_options)

    link_names = [x["option"] for x in config.needs_extra_links]
    for keyword in kwargs:
        if keyword not in needs_extra_options and keyword not in link_names:
            raise NeedsInvalidOption(
                "Unknown Option {}. "
                "Use needs_extra_options or needs_extra_links in conf.py"
                "to define this option.".format(keyword)
            )

    # Merge links
    copy_links = []

    for link_type in config.needs_extra_links:
        # Check, if specific link-type got some arguments during method call
        if (
            link_type["option"] not in list(kwargs.keys())
            and link_type["option"] not in needs_global_options.keys()
        ):
            # if not we set no links, but entry in needS_info must be there
            links = []
        elif link_type["option"] in needs_global_options.keys() and (
            link_type["option"] not in list(kwargs.keys())
            or len(str(kwargs[link_type["option"]])) == 0
        ):
            # If it is in global option, value got already set during prior handling of
            # them
            links_string = needs_info[link_type["option"]]
            links = utils.read_in_links(links_string)
        else:
            # if it is set in kwargs, take this value and maybe override set value from
            # global_options
            links_string = kwargs[link_type["option"]]
            links = utils.read_in_links(links_string)

        needs_info[link_type["option"]] = links
        needs_info["{}_back".format(link_type["option"])] = set()

        if "copy" not in link_type.keys():
            link_type["copy"] = False

        if link_type["copy"] and link_type["option"] != "links":
            copy_links += links  # Save extra links for main-links

    needs_info["links"] += copy_links  # Set copied links to main-links

    env.needs_all_needs[need_id] = needs_info

    # Template builds
    ##############################

    for template, content_type in [
        ("template", "content"),
        ("pre_template", "pre_content"),
        ("post_template", "post_content"),
    ]:
        if needs_info[template]:
            needs_info[content_type] = _prepare_template(app, needs_info, template)

    if needs_info["template"]:
        content = needs_info["content"]

    if needs_info["hide"]:
        return [target_node]

    # Adding of basic Need node.
    ############################
    # Title and meta data information gets added alter during event handling via
    # process_need_nodes(). We just add a basic need node and render the rst-based
    # content, because this can not be done later.
    style_classes = ["need", "need-{}".format(need_type_info.directive.lower())]
    if style:
        style_classes.append(style)

    node_need = sphinxcontrib.needs.directives.need.Need(
        '', classes=style_classes, ids=[need_id], refid=need_id)

    # Render rst-based content and add it to the need-node

    node_need_content = _render_template(content, docname, lineno, state)
    need_parts = find_parts(node_need_content)
    update_need_with_parts(env, needs_info, need_parts)

    node_need += node_need_content.children

    needs_info["content_node"] = node_need

    def add_container(node_list, content_type: str):
        if content_type in needs_info:
            content = _render_template(needs_info[content_type], docname, lineno, state)
            container = nodes.container()
            container += content.children
            node_list.append(container)

    return_nodes = []
    add_container(return_nodes, "pre_content")
    return_nodes.extend([target_node, node_need])
    add_container(return_nodes, "post_content")

    return return_nodes


def _split_tags(
    tags_string: Optional[str], need_id: str, allowed_tags: Optional[List[str]]
) -> List[str]:

    if not tags_string:
        return []

    def is_valid(tag: str) -> bool:
        if len(tag) == 0 or tag.isspace():
            logger.warning(
                "Scruffy tag definition found in need {}. "
                "Defined tag contains spaces only.".format(need_id)
            )
            return False

        if allowed_tags and tag not in allowed_tags:
            raise NeedsTagNotAllowed(
                "Tag {0} of need id {1} is not allowed "
                "by config value 'needs_tags'.".format(tag, need_id)
            )

        return True

    raw_tags = (tag.strip() for tag in re.split(";|,", tags_string))
    tags = filter(is_valid, raw_tags)

    return utils.fix_list_dyn_func(tags)


def _prepare_template(app: Sphinx, needs_info, template_key) -> str:
    template_folder = app.config.needs_template_folder
    if not os.path.isabs(template_folder):
        template_folder = os.path.join(app.confdir, template_folder)

    if not os.path.isdir(template_folder):
        raise NeedsTemplateException(
            "Template folder does not exist: {}".format(template_folder)
        )

    template_file_name = needs_info[template_key] + ".need"
    template_path = os.path.join(template_folder, template_file_name)
    if not os.path.isfile(template_path):
        raise NeedsTemplateException(
            "Template does not exist: {}".format(template_path)
        )

    with open(template_path, "r") as template_file:
        template_content = template_file.read()
    template_obj = Template(template_content)
    new_content = template_obj.render(**needs_info)

    return new_content


def _render_template(content: str, docname: str, lineno: int, state) -> nodes.Element:
    rst = ViewList()
    for line in content.split("\n"):
        rst.append(line, docname, lineno)
    node_need_content = nodes.Element()
    node_need_content.document = state.document
    nested_parse_with_titles(state, rst, node_need_content)
    return node_need_content


def make_hashed_id(
    prefix: str,
    content: str,
    id_length: Optional[int] = None,
) -> str:
    """
    Creates an ID based on title or need.
    Also cares about the correct prefix, which is specified for each need type.
    :param prefix: the prefix of the id of every need of this type
    :param content: the content to be hashed
    :param id_length: maximum length of the generated ID
    :return: ID as string
    """

    return "{}{}".format(
        prefix,
        hashlib.sha1(content.encode("UTF-8")).hexdigest().upper()[:id_length],
    )


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


def _merge_global_options(needs_info, global_options):
    """Add all global defined options to needs_info"""
    if global_options is None:
        return
    for key, value in global_options.items():

        # If key already exists in needs_info, this global_option got overwritten manually in current need
        if needs_info.get(key, None):
            continue

        if isinstance(value, tuple):
            values = [value]
        elif isinstance(value, list):
            values = value
        else:
            needs_info[key] = value
            continue

        for single_value in values:
            length = len(single_value)
            if not (length == 2 or length == 3):
                raise NeedsInvalidException(
                    "global option tuple has wrong amount of parameters: {}".format(key)
                )
            if filter_single_need(needs_info, single_value[1]):
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
