# -*- coding: utf-8 -*-

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst import Directive
from sphinx.errors import SphinxError
from jinja2 import Template

import hashlib
import re


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

        id = self.options.get("id",
                              "%s%s" % (type_prefix,
                                        hashlib.sha1(self.arguments[0].encode("UTF-8")).hexdigest().upper()
                                        [:env.app.config.needs_id_length]))

        if env.app.config.needs_id_regex and not re.match(env.app.config.needs_id_regex, id):
            raise NeedsInvalidException("Given ID '{id}' does not match configured regex '{regex}'".format(
                id=id, regex=env.app.config.needs_id_regex))

        # id = id.upper()

        # Calculate target id, to be able to set a link back
        target_id = id
        target_node = nodes.target('', '', ids=[target_id])

        collapse = str(self.options.get("collapse", ""))
        if isinstance(collapse, str) and len(collapse) > 0:
            if collapse.upper() in ["TRUE", 1, "YES"]:
                collapse = True
            elif collapse.upper() in ["FALSE", 0, "NO"]:
                collapse = False
            else:
                raise Exception("collapse attribute must be true or false")

        hide = True if "hide" in self.options.keys() else False
        hide_tags = True if "hide_tags" in self.options.keys() else False
        hide_status = True if "hide_status" in self.options.keys() else False
        title = self.arguments[0]
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
            raise NeedsDuplicatedId("A need with ID {0} already exists! This is not allowed".format(id))

        # Add the need and all needed information
        needs_info = {
            'docname': env.docname,
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
            'links': links,
            'title': title,
            'content': content,
            'collapse': collapse,
            'hide': hide,
            'hide_tags': hide_tags,
            'hide_status': hide_status,
        }
        self.merge_extra_options(needs_info)
        env.need_all_needs[id] = needs_info
        if collapse == "":
            if env.config.needs_collapse_details:
                template = Template(env.config.needs_template_collapse)
            else:
                template = Template(env.config.needs_template)
        elif collapse:
            template = Template(env.config.needs_template_collapse)
        else:
            template = Template(env.config.needs_template)

        text = template.render(**env.need_all_needs[id])
        self.state_machine.insert_input(
            text.split('\n'),
            self.state_machine.document.attributes['source'])

        return [target_node]

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


def purge_needs(app, env, docname):
    if not hasattr(env, 'need_all_needs'):
        return
    env.need_all_needs = {key: need for key, need in env.need_all_needs.items() if need['docname'] != docname}


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
        for key, current_need in needs.items():
            current_need["links_back"] = []
            for linked_key, linked_need in needs.items():
                if current_need["id"] in linked_need["links"]:
                    current_need["links_back"].append(linked_need["id"])


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
