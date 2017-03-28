import random
import hashlib
import string
from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst import Directive
from sphinx.util.compat import make_admonition
from sphinx.locale import _
from docutils.statemachine import ViewList
from sphinx.util import nested_parse_with_titles
from jinja2 import Template
from textwrap import dedent

DEFAULT_TEMPLATE = """
.. _{{id}}:

{{type_name}}: **{{title}}** ({{id}})

    {{content|indent(4) }}

    {% if status -%}
    **status**: {{status}}
    {% endif %}

    {% if tags -%}
    **tags**: {{"; ".join(tags)}}
    {% endif %}

    {% if links -%}
    **links**:
    {% for link in links -%}
        :ref:`{{link}} <{{link}}>` {%if loop.index < links|length -%}; {% endif -%}
    {% endfor -%}
    {% endif %}
"""


def setup(app):
    app.add_config_value('needs_types',
                         [dict(directive="req", title="Requirement", prefix="r_"),
                          dict(directive="spec", title="Specification", prefix="s_"),
                          dict(directive="impl", title="Implementation", prefix="i_"),
                          dict(directive="test", title="Test Case", prefix="t_"),
                          ],
                         'html')
    app.add_config_value('needs_template',
                         DEFAULT_TEMPLATE,
                         'html')
    app.add_config_value('needs_include_needs', True, 'html')
    app.add_config_value('needs_need_name', "Need", 'html')
    app.add_config_value('needs_spec_name', "Specification", 'html')
    app.add_config_value('needs_id_prefix_needs', "", 'html')
    app.add_config_value('needs_id_prefix_specs', "", 'html')
    app.add_config_value('needs_id_length', 5, 'html')
    app.add_config_value('needs_specs_show_needlist', False, 'html')

    # Define nodes
    app.add_node(need)
    app.add_node(needlist)
    app.add_directive("need", NeedDirective)

    # Define directives
    types = app.config.needs_types
    for type in types:
        type_directive = type["directive"]
        type_name = type["title"]
        type_prefix = type["prefix"]

        app.add_directive(type_directive, NeedDirective)
        app.add_directive("{0}_list".format(type_directive), NeedDirective)

    # app.add_directive('need', NeedDirective)
    app.add_directive('needlist', NeedlistDirective)

    # Make connections to events
    app.connect('env-purge-doc', purge_needs)
    app.connect('doctree-resolved', process_need_nodes)
    app.connect('doctree-resolved', process_need_nodelists)

    return {'version': '0.1'}  # identifies the version of our extension


class need(nodes.General, nodes.Element):
    pass


class needlist(nodes.General, nodes.Element):
    pass


#####################################################################################################
# NEEDS
#####################################################################################################
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
                   'show_linked_titles': directives.flag
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
        for type in types:
            if type["directive"] == self.name:
                type_name = type["title"]
                type_prefix = type["prefix"]
                break

        # Get the id or generate a random string/hash string, which is hopefully unique
        # TODO: Check, if id was already given. If True, recalculate id
        # id = self.options.get("id", ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for
        #  _ in range(5)))
        id = self.options.get("id",
                              "%s%s" % (type_prefix,
                                        hashlib.sha1(self.arguments[0].encode("UTF-8")).hexdigest().upper()
                                        [:env.app.config.needs_id_length]))

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
            links = [link.strip() for link in links.split(";") if link != ""]

        show_linked_titles = True if "show_linked_titles" in self.options.keys() else False

        #############################################################################################
        # Add need to global need list
        #############################################################################################
        # be sure, global var is available. If not, create it
        if not hasattr(env, 'need_all_needs'):
            env.need_all_needs = {}

        # Add the need and all needed information
        env.need_all_needs[id] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target': targetnode,
            'type': self.name,
            'type_name': type_name,
            'type_prefix': type_prefix,
            'status': status,
            'tags': tags,
            'id': id,
            'links': links,
            'title': title,
            'content': content,
            'hide': hide,
            'hide_tags': hide_tags,
            'hide_status': hide_status,
            'show_linked_titles': show_linked_titles
        }

        # self.state_machine.insert_input(
        #     [".. _link_{0}:\n".format(id)],
        #     self.state_machine.document.attributes['source'])

        template = Template(env.config.needs_template)
        self.state_machine.insert_input(
            template.render(**env.need_all_needs[id]).split('\n'),
            self.state_machine.document.attributes['source'])

        # for link in links:
        #     self.state_machine.insert_input(
        #         [":ref:`%s <%s>`" % (link, link)],
        #         self.state_machine.document.attributes['source'])

        return [targetnode]


class NeedlistDirective(Directive):
    def sort_by(argument):
        return directives.choice(argument, ("status", "id"))

    option_spec = {'status': directives.unicode_code,
                   'tags': directives.unicode_code,
                   'show_status': directives.flag,
                   'show_tags': directives.flag,
                   'show_filters': directives.flag,
                   'show_links': directives.flag,
                   'sort_by': sort_by}

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_needlists'):
            env.need_all_needlists = {}

        targetid = "need-%d" % env.new_serialno('need')
        targetnode = nodes.target('', '', ids=[targetid])

        tags = self.options.get("tags", [])
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(";")]

        status = self.options.get("status", [])
        if isinstance(status, str):
            status = [stat.strip() for stat in status.split(";")]

        # Add the need and all needed information
        env.need_all_needlists[targetid] = {
            'status': status,
            'tags': tags,
            'show_tags': True if self.options.get("show_tags", False) is None else False,
            'show_status': True if self.options.get("show_status", False) is None else False,
            'show_filters': True if self.options.get("show_filters", False) is None else False,
            'sort_by': self.options.get("sort_by", None)
        }

        return [targetnode] + [needlist('')]


def purge_needs(app, env, docname):
    if not hasattr(env, 'need_all_needs'):
        return
    env.need_all_needs = {key: need for key, need in env.need_all_needs.items() if need['docname'] != docname}


def process_need_nodes(app, doctree, fromdocname):
    if not app.config.needs_include_needs:
        for node in doctree.traverse(need):
            node.parent.remove(node)


def process_need_nodelists(app, doctree, fromdocname):
    # Replace all needlist nodes with a list of the collected needs.
    # Augment each need with a backlink to the original location.
    env = app.builder.env

    # NEEDLIST
    for node in doctree.traverse(needlist):
        if not app.config.needs_include_needs:
            # Ok, this is really dirty.
            # If we replace a node, docutils checks, if it will not lose any attributes.
            # But this is here the case, because we are using the attribute "ids" of a node.
            # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
            # before docutils claims about it.
            for att in ('ids', 'names', 'classes', 'dupnames'):
                node[att] = []
            node.replace_self([])
            continue

        content = []
        id = node.attributes["ids"][0]
        nodelist = env.need_all_needlists[id]

        all_needs = env.need_all_needs

        all_needs = list(all_needs.values())
        if nodelist["sort_by"] is not None:
            if nodelist["sort_by"] == "id":
                all_needs = sorted(all_needs, key=lambda node: node["id"])
            elif nodelist["sort_by"] == "status":
                all_needs = sorted(all_needs, key=status_sorter)

        for need_info in all_needs:
            status_filter_passed = False
            if need_info["status"] in nodelist["status"] or len(nodelist["status"]) == 0:
                status_filter_passed = True

            tags_filter_passed = False
            if len(set(need_info["tags"]) & set(nodelist["tags"])) > 0 or len(nodelist["tags"]) == 0:
                tags_filter_passed = True

            if status_filter_passed and tags_filter_passed:
                para = nodes.line()
                description = "%s: %s" % (need_info["id"], need_info["title"])

                if nodelist["show_status"] and need_info["status"] is not None:
                    description += " (%s)" % need_info["status"]

                if nodelist["show_tags"] and need_info["tags"] is not None:
                    description += " [%s]" % "; ".join(need_info["tags"])

                title = nodes.Text(description, description)

                # Create a reference
                if not need_info["hide"]:
                    ref = nodes.reference('', '')
                    ref['refdocname'] = need_info['docname']
                    ref['refuri'] = app.builder.get_relative_uri(
                        fromdocname, need_info['docname'])
                    ref['refuri'] += '#' + need_info['target']['refid']
                    ref.append(title)
                    para += ref
                else:
                    para += title

                content.append(para)

        if len(content) == 0:
            nothing_found = "No needs passed the filters"
            para = nodes.line()
            nothing_found_node = nodes.Text(nothing_found, nothing_found)
            para += nothing_found_node
            content.append(para)
        if nodelist["show_filters"]:
            para = nodes.paragraph()
            filter_text = "Used filter:"
            filter_text += " status(%s)" % " OR ".join(nodelist["status"]) if len(nodelist["status"]) > 0 else ""
            if len(nodelist["status"]) > 0 and len(nodelist["tags"]) > 0:
                filter_text += " AND "
            filter_text += " tags(%s)" % " OR ".join(nodelist["tags"]) if len(nodelist["tags"]) > 0 else ""
            filter_node = nodes.emphasis(filter_text, filter_text)
            para += filter_node
            content.append(para)

        node.replace_self(content)


def status_sorter(a):
    """
    Helper function to sort string elements, which can be None, too.
    :param a: element, which gets sorted
    :return:
    """
    if not a["status"]:
        return ""
    return a["status"]
