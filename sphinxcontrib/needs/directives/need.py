# -*- coding: utf-8 -*-
import hashlib
import re

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst import Directive
from sphinx.errors import SphinxError
from sphinx.util.nodes import nested_parse_with_titles
from docutils.statemachine import ViewList
from pkg_resources import parse_version
import sphinx
from sphinx.util.nodes import make_refnode

from sphinxcontrib.needs.roles.need_incoming import Need_incoming
from sphinxcontrib.needs.roles.need_outgoing import Need_outgoing
from sphinxcontrib.needs.roles.need_part import update_need_with_parts, find_parts
from sphinxcontrib.needs.functions import resolve_dynamic_values, find_and_replace_node_content

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging
logger = logging.getLogger(__name__)

NON_BREAKING_SPACE = re.compile('\xa0+')


class Need(nodes.General, nodes.Element):
    """
    Node for containing a complete need.
    Node structure:

    - need
      - headline container
      - meta container ()
      - content container

    As the content container gets rendered RST input, this must already be created during
    node handling and can not be done later during event handling.
    Reason: nested_parse_with_titles() needs self.state, which is available only during node handling.

    headline and content container get added later during event handling (process_need_nodes()).
    """
    child_text_separator = "\n"
    pass


class NeedDirective(Directive):
    """
    Collects mainly all needed need-information and renders its rst-based content.

    It only creates a basic node-structure to support later manipulation.
    """
    # this enables content in the directive
    has_content = True

    required_arguments = 1
    optional_arguments = 0
    option_spec = {'id': directives.unchanged_required,
                   'status': directives.unchanged_required,
                   'tags': directives.unchanged_required,
                   'links': directives.unchanged_required,
                   'collapse': directives.unchanged_required,
                   'hide': directives.flag,
                   'hide_tags': directives.flag,
                   'hide_status': directives.flag,
                   'hide_links': directives.flag,
                   'title_from_content': directives.flag}

    # add configured link types

    final_argument_whitespace = True

    def __init__(self, *args, **kw):
        super(NeedDirective, self).__init__(*args, **kw)
        self.log = logging.getLogger(__name__)
        self.full_title = self._get_full_title()

    def run(self):
        #############################################################################################
        # Get environment
        #############################################################################################
        env = self.env
        types = env.app.config.needs_types
        type_name = ""
        type_prefix = ""
        type_color = ""
        type_style = ""
        found = False
        for type in types:
            if type["directive"] == self.name:
                type_name = type["title"]
                type_prefix = type["prefix"]
                type_color = type["color"]
                type_style = type["style"]
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
        if "id" not in self.options.keys() and env.app.config.needs_id_required:
            raise NeedsNoIdException("An id is missing for this need and must be set, because 'needs_id_required' "
                                     "is set to True in conf.py")

        id = self.options.get("id", self.make_hashed_id(type_prefix, env.config.needs_id_length))

        if env.app.config.needs_id_regex and not re.match(env.app.config.needs_id_regex, id):
            raise NeedsInvalidException("Given ID '{id}' does not match configured regex '{regex}'".format(
                id=id, regex=env.app.config.needs_id_regex))

        # Calculate target id, to be able to set a link back
        target_node = nodes.target('', '', ids=[id])

        collapse = str(self.options.get("collapse", ""))
        if isinstance(collapse, str) and len(collapse) > 0:
            if collapse.upper() in ["TRUE", 1, "YES"]:
                collapse = True
            elif collapse.upper() in ["FALSE", 0, "NO"]:
                collapse = False
            else:
                raise Exception("collapse attribute must be true or false")
        else:
            collapse = getattr(env.app.config, "needs_collapse_details", True)

        hide = True if "hide" in self.options.keys() else False
        hide_tags = True if "hide_tags" in self.options.keys() else False
        hide_status = True if "hide_status" in self.options.keys() else False
        content = "\n".join(self.content)

        # Handle status
        status = self.options.get("status", None)
        # Check if status is in needs_statuses. If not raise an error.
        if env.app.config.needs_statuses:
            if status not in [stat["name"] for stat in env.app.config.needs_statuses]:
                raise NeedsStatusNotAllowed("Status {0} of need id {1} is not allowed "
                                            "by config value 'needs_statuses'.".format(status, id))

        tags = self.options.get("tags", [])
        if len(tags) > 0:
            # Not working regex.
            # test = re.match(r'^(?: *(\[\[.*?\]\]|[^,; ]+) *(?:,|;|$)?)+', tags)

            tags = [tag.strip() for tag in re.split(";|,", tags)]
            for i in range(len(tags)):
                if len(tags[i]) == 0 or tags[i].isspace():
                    del (tags[i])
                    logger.warning('Scruffy tag definition found in need {}. '
                                   'Defined tag contains spaces only.'.format(id))

            # Check if tag is in needs_tags. If not raise an error.
            if env.app.config.needs_tags:
                for tag in tags:
                    if tag not in [tag["name"] for tag in env.app.config.needs_tags]:
                        raise NeedsTagNotAllowed("Tag {0} of need id {1} is not allowed "
                                                 "by config value 'needs_tags'.".format(tag, id))
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

        if id in env.needs_all_needs.keys():
            if 'id' in self.options:
                raise NeedsDuplicatedId("A need with ID {} already exists! "
                                        "This is not allowed. Document {}[{}]".format(id, self.docname, self.lineno))
            else:  # this is a generated ID
                raise NeedsDuplicatedId(
                    "Needs could not generate a unique ID for a need with "
                    "the title '{}' because another need had the same title. "
                    "Either supply IDs for the requirements or ensure the "
                    "titles are different.  NOTE: If title is being generated "
                    "from the content, then ensure the first sentence of the "
                    "requirements are different.".format(' '.join(self.full_title)))

        # Add the need and all needed information
        needs_info = {
            'docname': self.docname,
            'lineno': self.lineno,
            'target_node': target_node,
            'type': self.name,
            'type_name': type_name,
            'type_prefix': type_prefix,
            'type_color': type_color,
            'type_style': type_style,
            'status': status,
            'tags': tags,
            'id': id,
            'title': self.trimmed_title,
            'full_title': self.full_title,
            'content': content,
            'collapse': collapse,
            'hide': hide,
            'hide_tags': hide_tags,
            'hide_status': hide_status,
            'parts': {},

            'is_part': False,
            'is_need': True
        }
        self.merge_extra_options(needs_info)
        self.merge_global_options(needs_info)

        # Merge links
        copy_links = []

        for link_type in env.config.needs_extra_links:
            links = self.read_in_links(link_type["option"])
            needs_info[link_type["option"]] = links
            needs_info['{}_back'.format(link_type["option"])] = set()

            if link_type['copy'] and link_type['option'] != 'links':
                copy_links += links

        needs_info['links'] += copy_links

        env.needs_all_needs[id] = needs_info

        if hide:
            return [target_node]

        # Adding of basic Need node.
        ############################
        # Title and meta data information gets added alter during event handling via process_need_nodes()
        # We just add a basic need node and render the rst-based content, because this can not be done later.
        node_need = Need('', classes=['need', self.name, 'need-{}'.format(type_name.lower())])

        # Render rst-based content and add it to the need-node
        rst = ViewList()
        for line in self.content:
            rst.append(line, self.docname, self.lineno)
        node_need_content = nodes.Element()
        node_need_content.document = self.state.document
        nested_parse_with_titles(self.state, rst, node_need_content)

        need_parts = find_parts(node_need_content)
        update_need_with_parts(env, needs_info, need_parts)

        node_need += node_need_content.children

        return [target_node] + [node_need]

    def read_in_links(self, name):
        # Get links
        links_string = self.options.get(name, [])
        links = []
        if len(links_string) > 0:
            # links = [link.strip() for link in re.split(";|,", links) if not link.isspace()]
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

    def make_hashed_id(self, type_prefix, id_length):
        hashable_content = self.full_title or '\n'.join(self.content)
        return "%s%s" % (type_prefix,
                         hashlib.sha1(hashable_content.encode("UTF-8"))
                         .hexdigest()
                         .upper()[:id_length])

    @property
    def env(self):
        return self.state.document.settings.env

    @property
    def title_from_content(self):
        return ('title_from_content' in self.options or
                self.env.config.needs_title_from_content)

    @property
    def docname(self):
        return self.state.document.settings.env.docname

    @property
    def trimmed_title(self):
        title = self.full_title
        max_length = self.max_title_length
        if max_length == -1 or len(title) <= max_length:
            return title
        elif max_length <= 3:
            return title[:self.max_title_length]
        else:
            return title[:self.max_title_length - 3] + '...'

    @property
    def max_title_length(self):
        return self.state.document.settings.env.config.needs_max_title_length

    def merge_extra_options(self, needs_info):
        """Add any extra options introduced via options_ext to needs_info"""
        extra_keys = set(self.options.keys()).difference(set(needs_info.keys()))
        for key in extra_keys:
            needs_info[key] = self.options[key]

        # Finally add all not used extra options with empty value to need_info.
        # Needed for filters, which need to access these empty/not used options.
        for key in self.option_spec:
            if key not in needs_info.keys():
                needs_info[key] = ""

        return extra_keys

    def merge_global_options(self, needs_info):
        """Add all global defined options to needs_info"""
        global_options = getattr(self.env.app.config, 'needs_global_options', None)
        if global_options is None:
            return
        for key, value in global_options.items():

            # If key already exists in needs_info, this global_option got overwritten manually in current need
            if key in needs_info.keys():
                continue

            needs_info[key] = value

    def _get_full_title(self):
        """Determines the title for the need in order of precedence:
        directive argument, first sentence of requirement (if
        `:title_from_content:` was set, and '' if no title is to be derived."""
        if len(self.arguments) > 0:  # a title was passed
            if 'title_from_content' in self.options:
                self.log.warning(
                    'Needs: need "{}" has :title_from_content: set, '
                    'but a title was provided. (see file {})'
                        .format(self.arguments[0], self.docname)
                )
            return self.arguments[0]
        elif self.title_from_content:
            first_sentence = ' '.join(self.content).split('.', 1)[0]
            if not first_sentence:
                raise NeedsInvalidException(':title_from_content: set, but '
                                            'no content provided. '
                                            '(Line {} of file {}'
                                            .format(self.lineno, self.docname))
            return first_sentence
        else:
            return ''


def get_sections(need_info):
    """Gets the hierarchy of the section nodes as a list starting at the
    section of the current need and then its parent sections"""
    sections = []
    current_node = need_info['target_node']
    while current_node:
        if isinstance(current_node, nodes.section):
            title = current_node.children[0].astext()
            # If using auto-section numbering, then Sphinx inserts
            # multiple non-breaking space unicode characters into the title
            # we'll replace those with a simple space to make them easier to
            # use in filters
            title = NON_BREAKING_SPACE.sub(' ', title)
            sections.append(title)
        current_node = getattr(current_node, 'parent', None)
    return sections


def purge_needs(app, env, docname):
    """
    Gets executed, if a doc file needs to be purged/ read in again.
    So this code delete all found needs for the given docname.
    """
    if not hasattr(env, 'needs_all_needs'):
        return
    env.needs_all_needs = {key: need for key, need in env.needs_all_needs.items() if need['docname'] != docname}


def add_sections(app, doctree, fromdocname):
    """Add section titles to the needs as additional attributes that can
    be used in tables and filters"""
    needs = getattr(app.builder.env, 'needs_all_needs', {})
    for key, need_info in needs.items():
        sections = get_sections(need_info)
        need_info['sections'] = sections
        need_info['section_name'] = sections[0] if sections else ""


def process_need_nodes(app, doctree, fromdocname):
    """
    Event handler to add title meta data (status, tags, links, ...) information to the Need node.

    :param app:
    :param doctree:
    :param fromdocname:
    :return:
    """
    if not app.config.needs_include_needs:
        for node in doctree.traverse(Need):
            node.parent.remove(node)
        return

    env = app.builder.env

    # If no needs were defined, we do not need to do anything
    if not hasattr(env, "needs_all_needs"):
        return

    needs = env.needs_all_needs

    # Call dynamic functions and replace related note data with their return values
    resolve_dynamic_values(env)

    # Create back links of common links and extra links
    for links in env.config.needs_extra_links:
        create_back_links(env, links['option'])

    for node_need in doctree.traverse(Need):
        need_id = node_need.attributes["ids"][0]
        need_data = needs[need_id]

        find_and_replace_node_content(node_need, env, need_data)

        node_headline = construct_headline(need_data, app)
        node_meta = construct_meta(need_data, env)

        # Collapse check
        if need_data["collapse"] and "HTML" in app.builder.name.upper():
            # HEADER
            node_need_toogle_container = nodes.container(classes=['toggle'])
            node_need_toogle_head_container = nodes.container(classes=['header'])
            node_need_toogle_head_container += node_headline.children

            node_need_toogle_container.append(node_need_toogle_head_container)

            # Only add node_meta(line_block), if it has lines in it
            # Otherwise the pdf/latex build will claim about an empty line_block.
            if node_meta.children:
                node_need_toogle_container.append(node_meta)

            node_need.insert(0, node_need_toogle_container)
        else:
            node_meta.insert(0, node_headline)
            node_need.insert(0, node_meta)


def create_back_links(env, option):
    """
    Create back-links in all found needs.
    But do this only once, as all needs are already collected and this sorting is for all
    needs and not only for the ones of the current document.

    :param env: sphinx enviroment
    :return: None
    """
    option_back = '{}_back'.format(option)
    if env.needs_workflow['backlink_creation_{}'.format(option)]:
        return

    needs = env.needs_all_needs
    for key, need in needs.items():
        for link in need[option]:
            link_main = link.split('.')[0]
            try:
                link_part = link.split('.')[1]
            except IndexError:
                link_part = None

            if link_main in needs:
                if key not in needs[link_main][option_back]:
                    needs[link_main][option_back].append(key)

                # Handling of links to need_parts inside a need
                if link_part is not None:
                    if link_part in needs[link_main]['parts']:
                        if option_back not in needs[link_main]['parts'][link_part].keys():
                            needs[link_main]['parts'][link_part][option_back] = []
                        needs[link_main]['parts'][link_part][option_back].append(key)

    env.needs_workflow['backlink_creation_{}'.format(option)] = True


def construct_headline(need_data, app):
    """
    Constructs the node-structure for the headline/title container
    :param need_data: need_info container
    :return: node
    """
    # need title calculation
    title_type = '{}: '.format(need_data["type_name"])
    title_headline = need_data["title"]
    title_id = "{}".format(need_data["id"])
    title_spacer = " "

    # need title
    node_type = nodes.inline(title_type, title_type, classes=["needs-type"])
    node_title = nodes.inline(title_headline, title_headline, classes=["needs-title"])

    nodes_id = nodes.inline(classes=["needs-id"])

    nodes_id_text = nodes.Text(title_id, title_id)
    id_ref = make_refnode(app.builder,
                          fromdocname=need_data['docname'],
                          todocname=need_data['docname'],
                          targetid=need_data['id'],
                          child=nodes_id_text.deepcopy(),
                          title=title_id)
    nodes_id += id_ref

    node_spacer = nodes.inline(title_spacer, title_spacer, classes=["needs-spacer"])

    headline_line = nodes.line(classes=["headline"])
    headline_line.append(node_type)
    headline_line.append(node_spacer)
    headline_line.append(node_title)
    headline_line.append(node_spacer)
    headline_line.append(nodes_id)

    return headline_line


def construct_meta(need_data, env):
    """
    Constructs the node-structure for the status container
    :param need_data: need_info container
    :return: node
    """

    hide_options = env.config.needs_hide_options
    if not isinstance(hide_options, list):
        raise SphinxError('Config parameter needs_hide_options must be of type list')

    node_meta = nodes.line_block(classes=['needs_meta'])
    # need parameters
    param_status = "status: "
    param_tags = "tags: "

    if need_data["status"] is not None and 'status' not in hide_options:
        status_line = nodes.line(classes=['status'])
        # node_status = nodes.line(param_status, param_status, classes=['status'])
        node_status = nodes.inline(param_status, param_status, classes=['status'])
        status_line.append(node_status)
        status_line.append(nodes.inline(need_data["status"], need_data["status"],
                                        classes=["needs-status", str(need_data['status'])]))
        node_meta.append(status_line)

    if need_data["tags"] and 'tags' not in hide_options:
        tag_line = nodes.line(classes=['tags'])
        # node_tags = nodes.line(param_tags, param_tags, classes=['tags'])
        node_tags = nodes.inline(param_tags, param_tags, classes=['tags'])
        tag_line.append(node_tags)
        for tag in need_data['tags']:
            # node_tags.append(nodes.inline(tag, tag, classes=["needs-tag", str(tag)]))
            # node_tags.append(nodes.inline(' ', ' '))
            tag_line.append(nodes.inline(tag, tag, classes=["needs-tag", str(tag)]))
            tag_line.append(nodes.inline(' ', ' '))
        node_meta.append(tag_line)

    # Links incoming
    for link_type in env.config.needs_extra_links:
        link_back = '{}_back'.format(link_type['option'])
        if need_data[link_back] and link_back not in hide_options:
            node_incoming_line = nodes.line(classes=[link_type['option'], 'incoming'])
            prefix = "{}: ".format(link_type['incoming'])
            node_incoming_prefix = nodes.inline(prefix, prefix)
            node_incoming_line.append(node_incoming_prefix)
            node_incoming_links = Need_incoming(reftarget=need_data['id'], link_type=link_back)
            node_incoming_links.append(nodes.inline(need_data['id'], need_data['id']))
            node_incoming_line.append(node_incoming_links)
            node_meta.append(node_incoming_line)

    # Links outgoing
    for link_type in env.config.needs_extra_links:
        link = '{}'.format(link_type['option'])
        if need_data[link] and link not in hide_options:
            node_outgoing_line = nodes.line(classes=[link_type['option'], 'outgoing'])
            prefix = "{}: ".format(link_type['outgoing'])
            node_outgoing_prefix = nodes.inline(prefix, prefix)
            node_outgoing_line.append(node_outgoing_prefix)
            node_outgoing_links = Need_outgoing(reftarget=need_data['id'], link_type=link)
            node_outgoing_links.append(nodes.inline(need_data['id'], need_data['id']))
            node_outgoing_line.append(node_outgoing_links)
            node_meta.append(node_outgoing_line)

    extra_options = getattr(env.config, 'needs_extra_options', {})
    node_extra_options = []
    for key, value in extra_options.items():
        if key in hide_options:
            continue
        param_data = need_data[key]
        if param_data is None or not param_data:
            continue
        param_option = '{}: '.format(key)
        option_line = nodes.line(classes=['extra_option'])
        option_line.append(nodes.inline(param_option, param_option, classes=['extra_option']))
        option_line.append(nodes.inline(param_data, param_data,
                                        classes=["needs-extra-option", str(key)]))
        node_extra_options.append(option_line)

    node_meta += node_extra_options

    global_options = getattr(env.config, 'needs_global_options', {})
    node_global_options = []
    for key, value in global_options.items():
        # If a global option got locally overwritten, it must already part of extra_options.
        # In this skipp output, as this is done during extra_option handling
        if key in extra_options or key in hide_options:
            continue

        param_data = need_data[key]
        if param_data is None or not param_data:
            continue
        param_option = '{}: '.format(key)
        global_option_line = nodes.line(classes=['global_option'])
        global_option_line.append(nodes.inline(param_option, param_option, classes=['global_option']))
        global_option_line.append(nodes.inline(param_data, param_data,
                                               classes=["needs-global-option", str(key)]))
        node_global_options.append(global_option_line)

    node_meta += node_global_options

    return node_meta


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


#####################
# Visitor functions #
#####################
# Used for builders like html or latex to tell them, what do, if they stumble on a Need-Node in the doctree.
# Normally nothing needs to be done, as all needed output-configuration is done in the child-nodes of the detected
# Need-Node.


def html_visit(self, node):
    """
    Visitor method for Need-node of builder 'html'.
    Does only wrap the Need-content into an extra <div> with class=need
    """
    self.body.append(self.starttag(node, 'div', '', CLASS='need'))


def html_depart(self, node):
    self.body.append('</div>')


def latex_visit(self, node):
    pass


def latex_depart(self, node):
    pass


class NeedsNoIdException(SphinxError):
    pass


class NeedsDuplicatedId(SphinxError):
    pass


class NeedsStatusNotAllowed(SphinxError):
    pass


class NeedsTagNotAllowed(SphinxError):
    pass


class NeedsInvalidException(SphinxError):
    pass
