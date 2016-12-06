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


def setup(app):
    app.add_config_value('need_include_needs', True, 'html')
    app.add_config_value('need_name', "Need", 'html')

    # Define nodes
    app.add_node(needlist)
    app.add_node(need,
                 html=(visit_need_node, depart_need_node),
                 latex=(visit_need_node, depart_need_node),
                 text=(visit_need_node, depart_need_node))

    # Define directives
    app.add_directive('need', NeedDirective)
    app.add_directive('needlist', NeedlistDirective)

    # Make connections to events
    app.connect('doctree-resolved', process_need_nodes)
    app.connect('env-purge-doc', purge_needs)

    return {'version': '0.1'}  # identifies the version of our extension


class need(nodes.Admonition, nodes.Element):
    pass


class needlist(nodes.General, nodes.Element):
    pass


def visit_need_node(self, node):
    self.visit_admonition(node)


def depart_need_node(self, node):
    self.depart_admonition(node)


class NeedlistDirective(Directive):

    def sort_by(argument):
        return directives.choice(argument, ("status", "id"))

    option_spec = {'status': directives.unicode_code,
                   'tags': directives.unicode_code,
                   'show_status': directives.flag,
                   'show_tags': directives.flag,
                   'show_filters': directives.flag,
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


class NeedDirective(Directive):
    # this enables content in the directive
    has_content = True

    required_arguments = 1
    optional_arguments = 0
    option_spec = {'id': directives.unicode_code,
                   'status': directives.unicode_code,
                   'hide': directives.flag,
                   'tags': directives.unicode_code}

    final_argument_whitespace = True

    def run(self):
        #############################################################################################
        # Get environment
        #############################################################################################
        env = self.state.document.settings.env
        if not hasattr(env.app.config, "need_name"):
            need_name = "Need"
        else:
            need_name = env.app.config.need_name

        # Calculate target id, to be able to set a link back
        targetid = "need-%d" % env.new_serialno('need')
        targetnode = nodes.target('', '', ids=[targetid])

        # Get the id or generate a random string/hash string, which is hopefully unique
        # TODO: Check, if id was already given. If True, recalculate id
        # id = self.options.get("id", ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for
        #  _ in range(5)))
        id = self.options.get("id", hashlib.sha1(self.arguments[0].encode("UTF-8")).hexdigest().upper()[:5])

        hide = True if "hide" in self.options.keys() else False
        hide_tags = True if "hide_tags" in self.options.keys() else False
        hide_status = True if "hide_status" in self.options.keys() else False
        name = self.arguments[0]
        status = self.options.get("status", None)
        tags = self.options.get("tags", [])
        if len(tags) > 0:
            tags = [tag.strip() for tag in tags.split(";")]

        #############################################################################################
        # Define Layout of a need
        #############################################################################################
        title_text = '%s **%s** (%s)' % (need_name, name, id)

        ad = make_admonition(need, self.name, [title_text], self.options,
                             self.content, self.lineno, self.content_offset,
                             self.block_text, self.state, self.state_machine)

        if status is not None:
            meta_line = nodes.line()
            meta_line += nodes.Text("status: ", "status: ")
            meta_line += nodes.strong(status, status)
            ad[0] += meta_line

        if len(tags) > 0:
            meta_line = nodes.line()
            meta_line += nodes.Text(" tags: ", " tags: ")
            tag_text = "; ".join(tags)
            meta_line += nodes.strong(tag_text, tag_text)
            ad[0] += meta_line

        #############################################################################################
        # Add need to global need list
        #############################################################################################
        # be sure, global var is available. If not, create it
        if not hasattr(env, 'need_all_needs'):
            env.need_all_needs = []

        # Add the need and all needed information
        env.need_all_needs.append({
            'docname': env.docname,
            'lineno': self.lineno,
            'need': ad[0],
            'target': targetnode,
            'status': status,
            'tags': tags,
            'id': id,
            'name': name,
            'hide': hide,
            'hide_tags': hide_tags,
            'hide_status': hide_status
        })

        if hide:
            return []

        return [targetnode] + ad


def purge_needs(app, env, docname):
    if not hasattr(env, 'need_all_needs'):
        return
    env.need_all_needs = [need for need in env.need_all_needs if need['docname'] != docname]


def process_need_nodes(app, doctree, fromdocname):
    if not app.config.need_include_needs:
        for node in doctree.traverse(need):
            node.parent.remove(node)

    # Replace all needlist nodes with a list of the collected needs.
    # Augment each need with a backlink to the original location.
    env = app.builder.env

    # NEEDLIST
    for node in doctree.traverse(needlist):
        if not app.config.need_include_needs:
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
                description = "%s: %s" % (need_info["id"], need_info["name"])

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
