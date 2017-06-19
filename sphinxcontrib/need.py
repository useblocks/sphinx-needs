# -*- coding: utf-8 -*-

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst import Directive
from sphinx.errors import SphinxError
from jinja2 import Template

import hashlib


class Need(nodes.General, nodes.Element):
    pass


class NeedDirective(Directive):
    # this enables content in the directive
    has_content = True

    required_arguments = 1
    optional_arguments = 0
    option_spec = {'id': directives.unicode_code,
                   'status': directives.unicode_code,
                   'tags': directives.unicode_code,
                   'links': directives.unicode_code,
                   'hide': directives.flag,
                   'hide_tags': directives.flag,
                   'hide_status': directives.flag,
                   'hide_links': directives.flag,
                   }

    # add configured link types

    final_argument_whitespace = True

    def run(self):
        #############################################################################################
        # Get environment
        #############################################################################################
        env = self.state.document.settings.env

        types = env.app.config.needs_types
        type_name = ""
        type_prefix = ""
        type_color = ""
        for type in types:
            if type["directive"] == self.name:
                type_name = type["title"]
                type_prefix = type["prefix"]
                type_color = type["color"]
                type_style = type["style"]
                break

        # Get the id or generate a random string/hash string, which is hopefully unique
        # TODO: Check, if id was already given. If True, recalculate id
        # id = self.options.get("id", ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for
        #  _ in range(5)))
        if "id" not in self.options.keys() and env.app.config.needs_id_required:
            raise NeedsNoIdException("An id is missing for this need and must be set, because 'needs_id_required' "
                                     "is set to True in conf.py")

        id = self.options.get("id",
                              "%s%s" % (type_prefix,
                                        hashlib.sha1(self.arguments[0].encode("UTF-8")).hexdigest().upper()
                                        [:env.app.config.needs_id_length]))

        id = id.upper()

        # Calculate target id, to be able to set a link back
        targetid = id
        targetnode = nodes.target('', '', ids=[targetid])

        hide = True if "hide" in self.options.keys() else False
        hide_tags = True if "hide_tags" in self.options.keys() else False
        hide_status = True if "hide_status" in self.options.keys() else False
        title = self.arguments[0]
        content = "\n".join(self.content)
        status = self.options.get("status", None)
        tags = self.options.get("tags", [])
        if len(tags) > 0:
            tags = [tag.strip() for tag in tags.split(";")]

        # Get links
        links = self.options.get("links", [])
        if len(links) > 0:
            links = [link.strip().upper() for link in links.split(";") if link != ""]

        #############################################################################################
        # Add need to global need list
        #############################################################################################
        # be sure, global var is available. If not, create it
        if not hasattr(env, 'need_all_needs'):
            env.need_all_needs = {}

        if id in env.need_all_needs.keys():
            raise NeedsDuplicatedId("A need with ID {0} already exists! This is not allowed".format(id))

        # Add the need and all needed information
        env.need_all_needs[id] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target': targetnode,
            'type': self.name,
            'type_name': type_name,
            'type_prefix': type_prefix,
            'type_color': type_color,
            'type_style': type_style,
            'status': status,
            'tags': tags,
            'id': id,
            'links': links,
            'title': title,
            'content': content,
            'hide': hide,
            'hide_tags': hide_tags,
            'hide_status': hide_status,
        }

        template = Template(env.config.needs_template)
        self.state_machine.insert_input(
            template.render(**env.need_all_needs[id]).split('\n'),
            self.state_machine.document.attributes['source'])

        return [targetnode]


def purge_needs(app, env, docname):
    if not hasattr(env, 'need_all_needs'):
        return
    env.need_all_needs = {key: need for key, need in env.need_all_needs.items() if need['docname'] != docname}


def process_need_nodes(app, doctree, fromdocname):
    if not app.config.needs_include_needs:
        for node in doctree.traverse(Need):
            node.parent.remove(node)
    else:
        # Wen need to get the back_links/incoming_links and store them
        # inside each need
        env = app.builder.env
        needs = env.need_all_needs
        for key, current_need in needs.items():
            current_need["links_back"] = []
            for linked_key, linked_need in needs.items():
                if current_need["id"] in linked_need["links"]:
                    current_need["links_back"].append(linked_need["id"])


class NeedsNoIdException(SphinxError):
    pass


class NeedsDuplicatedId(SphinxError):
    pass
