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
from sphinxcontrib.needs.roles.need_incoming import Need_incoming
from sphinxcontrib.needs.roles.need_outgoing import Need_outgoing

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging

NON_BREAKING_SPACE = re.compile('\xa0+')


class Need(nodes.General, nodes.Element):
    pass


class NeedDirective(Directive):
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
                   'title_from_content': directives.flag,
                   }

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
            # In this case the configuration from a prior sphinx run may be active, which has requisterd a direcitve,
            # which is reused inside a current document, but no type was defined for the current run...
            # Yeeeh, this really may happen...
            return [nodes.Text('', '')]

        # Get the id or generate a random string/hash string, which is hopefully unique
        # TODO: Check, if id was already given. If True, recalculate id
        # id = self.options.get("id", ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for
        #  _ in range(5)))
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
            tags = [tag.strip() for tag in re.split(";|,", tags)]
            for i in range(len(tags)):
                if len(tags[i]) == 0:
                    del(tags[i])
            # Check if tag is in needs_tags. If not raise an error.
            if env.app.config.needs_tags:
                for tag in tags:
                    if tag not in [tag["name"] for tag in env.app.config.needs_tags]:
                        raise NeedsTagNotAllowed("Tag {0} of need id {1} is not allowed "
                                                 "by config value 'needs_tags'.".format(tag, id))

        # Get links
        links = self.options.get("links", [])
        if len(links) > 0:
            # links = [link.strip().upper() for link in links.split(";") if link != ""]
            links = [link.strip() for link in re.split(";|,", links) if link != ""]

        #############################################################################################
        # Add need to global need list
        #############################################################################################
        # be sure, global var is available. If not, create it
        if not hasattr(env, 'need_all_needs'):
            env.need_all_needs = {}

        if id in env.need_all_needs.keys():
            if 'id' in self.options:
                raise NeedsDuplicatedId("A need with ID {0} already exists! "
                                        "This is not allowed".format(id))
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
            'links_back': set(),
            'target_node': target_node,
            'type': self.name,
            'type_name': type_name,
            'type_prefix': type_prefix,
            'type_color': type_color,
            'type_style': type_style,
            'status': status,
            'tags': tags,
            'id': id,
            'links': links,
            'title': self.trimmed_title,
            'full_title': self.full_title,
            'content': content,
            'collapse': collapse,
            'hide': hide,
            'hide_tags': hide_tags,
            'hide_status': hide_status,
        }
        extra_options = self.merge_extra_options(needs_info)
        env.need_all_needs[id] = needs_info

        # OLD CODE: using state machine
        # if collapse == "":
        #     if env.config.needs_collapse_details:
        #         template = Template(env.config.needs_template_collapse)
        #     else:
        #         template = Template(env.config.needs_template)
        # elif collapse:
        #     template = Template(env.config.needs_template_collapse)
        # else:
        #     template = Template(env.config.needs_template)
        #
        # text = template.render(**env.need_all_needs[id])
        # self.state_machine.insert_input(
        #     text.split('\n'),
        #     self.state_machine.document.attributes['source'])

        if hide:
            return [target_node]

        rst = ViewList()
        for line in self.content:
            rst.append(line, self.docname, self.lineno)

        node_need = Need('', classes=['need', self.name, 'need-{}'.format(type_name.lower())])

        # need title calculation
        title_type = '{}: '.format(needs_info["type_name"])
        title_headline = needs_info["title"]
        title_id = "{}".format(needs_info["id"])
        title_spacer = " "

        # need title
        node_type = nodes.inline(title_type, title_type, classes=["needs-type"])
        node_title = nodes.inline(title_headline, title_headline, classes=["needs-title"])
        nodes_id = nodes.inline(title_id, title_id, classes=["needs-id"])
        node_spacer = nodes.inline(title_spacer, title_spacer, classes=["needs-spacer"])

        # need parameters
        param_status = "status: "
        param_tags = "tags: "

        param_extra_options = {}
        for option in extra_options:
            param_extra_options[option] = self.options.get(option)

        node_status = nodes.line(param_status, param_status, classes=['status'])
        node_status.append(nodes.inline(needs_info["status"], needs_info["status"],
                                        classes=["needs-status", str(needs_info['status'])]))

        node_tags = nodes.line(param_tags, param_tags, classes=['tags'])
        for tag in needs_info['tags']:
            node_tags.append(nodes.inline(tag, tag, classes=["needs-tag", str(tag)]))
            node_tags.append(nodes.inline(' ', ' '))

        # Links incoming
        node_incoming = nodes.line()
        prefix = "links incoming: "
        node_incoming_prefix = nodes.Text(prefix, prefix)
        node_incoming.append(node_incoming_prefix)
        node_incoming_links = Need_incoming(reftarget=id)
        node_incoming_emphasis = nodes.emphasis('', '')
        node_incoming_emphasis.append(nodes.Text(id, id))
        node_incoming_links.append(node_incoming_emphasis)
        node_incoming.append(node_incoming_links)

        # Links outgoing
        node_outgoing = nodes.line()
        prefix = "links outgoing: "
        node_outgoing_prefix = nodes.Text(prefix, prefix)
        node_outgoing.append(node_outgoing_prefix)
        node_outgoing_links = Need_outgoing(reftarget=id)
        node_outgoing_emphasis = nodes.emphasis('', '')
        node_outgoing_emphasis.append(nodes.Text(id, id))
        node_outgoing_links.append(node_outgoing_emphasis)
        node_outgoing.append(node_outgoing_links)

        nodes_extra_options = []
        for key, value in param_extra_options.items():
            param_option = '{}: '.format(key)
            node_option = nodes.line(param_option, param_option, classes=['extra_option'])
            node_option.append(nodes.inline(value, value,
                                            classes=["needs-extra-option", str(key)]))

            nodes_extra_options.append(node_option)

        # Collapse check
        if needs_info["collapse"]:
            # HEADER
            node_need_toogle_container = nodes.container(classes=['toggle'])
            node_need_toogle_head_container = nodes.container(classes=['header'])
            node_need_toogle_head_container += node_type, node_spacer, node_title, node_spacer, nodes_id

            node_need_toogle_container.append(node_need_toogle_head_container)

            # PARAMETERS
            if needs_info["status"]:
                node_need_toogle_container.append(node_status)
            if needs_info["tags"]:
                node_need_toogle_container.append(node_tags)

            node_need_toogle_container.append(node_incoming)
            node_need_toogle_container.append(node_outgoing)

            node_need_toogle_container += nodes_extra_options
            node_need.append(node_need_toogle_container)
        else:
            node_headline = nodes.line()
            node_headline += node_type, node_spacer, node_title, node_spacer, nodes_id
            node_need.append(node_headline)
            if needs_info["status"]:
                node_need.append(node_status)
            if needs_info["tags"]:
                node_need.append(node_tags)

            node_need.append(node_incoming)
            node_need.append(node_outgoing)
            node_need += nodes_extra_options

        # need content calculation (parse RST content)
        node_need_content = nodes.Element()
        node_need_content.document = self.state.document
        nested_parse_with_titles(self.state, rst, node_need_content)

        node_need += node_need_content.children

        return [target_node] + [node_need]

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
    if not hasattr(env, 'need_all_needs'):
        return
    env.need_all_needs = {key: need for key, need in env.need_all_needs.items() if need['docname'] != docname}


def add_sections(app, doctree, fromdocname):
    """Add section titles to the needs as additional attributes that can
    be used in tables and filters"""
    needs = getattr(app.builder.env, 'need_all_needs', {})
    for key, need_info in needs.items():
        sections = get_sections(need_info)
        need_info['sections'] = sections
        need_info['section_name'] = sections[0] if sections else ""


def process_need_nodes(app, doctree, fromdocname):
    if not app.config.needs_include_needs:
        for node in doctree.traverse(Need):
            node.parent.remove(node)
    else:
        # We need to get the back_links/incoming_links and store them
        # inside each need
        env = app.builder.env

        # If no needs were defined, we do not need to do anything
        if not hasattr(env, "need_all_needs"):
            return

        needs = env.need_all_needs
        for key, need in needs.items():
            for link in need["links"]:
                if link in needs:
                    needs[link]["links_back"].add(key)

    # for node in doctree.traverse(Need):
    #     if not app.config.needs_include_needs:
    #         # Ok, this is really dirty.
    #         # If we replace a node, docutils checks, if it will not lose any attributes.
    #         # But this is here the case, because we are using the attribute "ids" of a node.
    #         # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
    #         # before docutils claims about it.
    #         for att in ('ids', 'names', 'classes', 'dupnames'):
    #             node[att] = []
    #         node.replace_self([])

        # content = nodes.Text("Buh", "Buh")
        # node.replace_self(content)


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
