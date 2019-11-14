import hashlib
import re
from docutils import nodes
from sphinxcontrib.needs.api.exceptions import NeedsNoIdException, NeedsInvalidException, NeedsStatusNotAllowed, \
     NeedsTagNotAllowed, NeedsDuplicatedId, NeedsInvalidOption
import sphinxcontrib.needs.directives.need
from sphinx.util.nodes import nested_parse_with_titles
from sphinxcontrib.needs.roles.need_part import update_need_with_parts, find_parts
import sphinx
from docutils.statemachine import ViewList
from pkg_resources import parse_version
sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging


logger = logging.getLogger(__name__)


def add_need(app, state, docname, lineno, need_type, title, id=None, content="", status=None, tags=None,
             links_string=None, hide=False, hide_tags=False, hide_status=False, collapse=True, style=None, **kwargs):
    """
    Creates a new need and returns its node.

    ``add_need`` allows to create needs programmatically and use its returned node to be integrated in any
    docutils based structure.

    ``kwags`` can contain options defined in ``needs_extra_options`` and ``needs_extra_links``.
    If an entry is found in ``kwags``, which *is not* specified in the configuration or registered e.g. via
    ``add_extra_option``, an exception is raised.

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
    :param hide_tags: boolean value.
    :param hide_status: boolean value.
    :param collapse: boolean value.
    :param style: String value of class attribute of node.

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
            type_color = ntype["color"]
            type_style = ntype["style"]
            found = True
            break
    if not found:
        # This should never happen. But it may happen, if Sphinx is called multiples times
        # inside one ongoing python process.
        # In this case the configuration from a prior sphinx run may be active, which has registered a directive,
        # which is reused inside a current document, but no type was defined for the current run...
        # Yeah, this really has happened...
        return [nodes.Text('', '')]

    # Get the id or generate a random string/hash string, which is hopefully unique
    # TODO: Check, if id was already given. If True, recalculate id
    # id = self.options.get("id", ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for
    # _ in range(5)))
    if id is None and env.app.config.needs_id_required:
        raise NeedsNoIdException("An id is missing for this need and must be set, because 'needs_id_required' "
                                 "is set to True in conf.py")

    if id is None:
        need_id = make_hashed_id(app, need_type, title, content)
    else:
        need_id = id

    if env.app.config.needs_id_regex and not re.match(env.app.config.needs_id_regex, need_id):
        raise NeedsInvalidException("Given ID '{id}' does not match configured regex '{regex}'".format(
            id=need_id, regex=env.app.config.needs_id_regex))

    # Calculate target id, to be able to set a link back
    target_node = nodes.target('', '', ids=[need_id])

    if collapse is None:
        collapse = getattr(env.app.config, "needs_collapse_details", True)

    # Handle status
    # Check if status is in needs_statuses. If not raise an error.
    if env.app.config.needs_statuses:
        if status not in [stat["name"] for stat in env.app.config.needs_statuses]:
            raise NeedsStatusNotAllowed("Status {0} of need id {1} is not allowed "
                                        "by config value 'needs_statuses'.".format(status, need_id))

    if tags is None:
        tags = []
    if len(tags) > 0:
        tags = [tag.strip() for tag in re.split(";|,", tags)]
        for i in range(len(tags)):
            if len(tags[i]) == 0 or tags[i].isspace():
                del (tags[i])
                logger.warning('Scruffy tag definition found in need {}. '
                               'Defined tag contains spaces only.'.format(need_id))

        # Check if tag is in needs_tags. If not raise an error.
        if env.app.config.needs_tags:
            for tag in tags:
                if tag not in [tag["name"] for tag in env.app.config.needs_tags]:
                    raise NeedsTagNotAllowed("Tag {0} of need id {1} is not allowed "
                                             "by config value 'needs_tags'.".format(tag, need_id))
        # This may have cut also dynamic function strings, as they can contain , as well.
        # So let put them together again
        # ToDo: There may be a smart regex for the splitting. This would avoid this mess of code...
    tags = _fix_list_dyn_func(tags)

    #############################################################################################
    # Add need to global need list
    #############################################################################################
    # be sure, global var is available. If not, create it
    if not hasattr(env, 'needs_all_needs'):
        env.needs_all_needs = {}

    if need_id in env.needs_all_needs.keys():
        if id is not None:
            raise NeedsDuplicatedId("A need with ID {} already exists! "
                                    "This is not allowed. Document {}[{}]".format(need_id, docname, lineno))
        else:  # this is a generated ID
            raise NeedsDuplicatedId(
                "Needs could not generate a unique ID for a need with "
                "the title '{}' because another need had the same title. "
                "Either supply IDs for the requirements or ensure the "
                "titles are different.  NOTE: If title is being generated "
                "from the content, then ensure the first sentence of the "
                "requirements are different.".format(' '.join(title)))

    # Trim title if it is too long
    max_length = getattr(env.app.config, 'needs_max_title_length', 30)
    if max_length == -1 or len(title) <= max_length:
        trimmed_title = title
    elif max_length <= 3:
        trimmed_title = title[:max_length]
    else:
        trimmed_title = title[:max_length - 3] + '...'

    # Add the need and all needed information
    needs_info = {
        'docname': docname,
        'lineno': lineno,
        'target_node': target_node,
        'type': need_type,
        'type_name': type_name,
        'type_prefix': type_prefix,
        'type_color': type_color,
        'type_style': type_style,
        'status': status,
        'tags': tags,
        'id': need_id,
        'title': trimmed_title,
        'full_title': title,
        'content': content,
        'collapse': collapse,
        'style': style,
        'hide': hide,
        'hide_tags': hide_tags,
        'hide_status': hide_status,
        'parts': {},

        'is_part': False,
        'is_need': True
    }
    needs_extra_options = env.config.needs_extra_options.keys()
    _merge_extra_options(needs_info, kwargs, needs_extra_options)

    needs_global_options = env.config.needs_global_options
    _merge_global_options(needs_info, needs_global_options)

    link_names = [x['option'] for x in env.config.needs_extra_links]
    for keyword in kwargs:
        if keyword not in needs_extra_options and keyword not in link_names:
            raise NeedsInvalidOption('Unknown Option {}. '
                                     'Use needs_extra_options or needs_extra_links in conf.py'
                                     'to define this option.'.format(keyword))

    # Merge links
    copy_links = []

    for link_type in env.config.needs_extra_links:
        # Check, if specific link-type got some arguments during method call
        if link_type['option'] not in list(kwargs.keys()):
            # if not we set no links, but entry in needS_info must be there
            links = []
        else:
            # if yes, parse string and get links
            links_string = kwargs[link_type['option']]
            links = _read_in_links(links_string)

        needs_info[link_type["option"]] = links
        needs_info['{}_back'.format(link_type["option"])] = set()

        if link_type['copy'] and link_type['option'] != 'links':
            copy_links += links  # Save extra links for main-links

    needs_info['links'] += copy_links  # Set copied links to main-links

    env.needs_all_needs[need_id] = needs_info

    if hide:
        return [target_node]

    # Adding of basic Need node.
    ############################
    # Title and meta data information gets added alter during event handling via process_need_nodes()
    # We just add a basic need node and render the rst-based content, because this can not be done later.
    style_classes = ['need', type_name, 'need-{}'.format(type_name.lower())]
    if style is not None and style is not '':
        style_classes.append(style)

    node_need = sphinxcontrib.needs.directives.need.Need(
        '', classes=style_classes)

    # Render rst-based content and add it to the need-node
    rst = ViewList()
    for line in content.split('\n'):
        rst.append(line, docname, lineno)
    node_need_content = nodes.Element()
    node_need_content.document = state.document
    nested_parse_with_titles(state, rst, node_need_content)

    need_parts = find_parts(node_need_content)
    update_need_with_parts(env, needs_info, need_parts)

    node_need += node_need_content.children

    return [target_node] + [node_need]


def _read_in_links(links_string):
    # Get links
    links = []
    if len(links_string) > 0:
        for link in re.split(";|,", links_string):
            if not link.isspace():
                links.append(link.strip())
            else:
                logger.warning('Grubby link definition found in need {}. '
                               'Defined link contains spaces only.'.format(id))

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
        raise NeedsInvalidException('Given need_type {} is unknown'.format(need_type))

    hashable_content = full_title or '\n'.join(content)
    return "%s%s" % (type_prefix,
                     hashlib.sha1(hashable_content.encode("UTF-8"))
                     .hexdigest()
                     .upper()[:id_length])


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
        if '[[' in element:
            open_func_string = True
            new_link = [element]
        elif ']]' in element:
            new_link.append(element)
            open_func_string = False
            element = ",".join(new_link)
            new_list.append(element)
        elif open_func_string:
            new_link.append(element)
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


def _merge_global_options(needs_info, global_options):
    """Add all global defined options to needs_info"""
    if global_options is None:
        return
    for key, value in global_options.items():

        # If key already exists in needs_info, this global_option got overwritten manually in current need
        if key in needs_info.keys():
            continue

        needs_info[key] = value


