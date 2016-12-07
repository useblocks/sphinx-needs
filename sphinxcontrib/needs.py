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
    app.add_config_value('needs_include_needs', True, 'html')
    app.add_config_value('needs_include_specs', True, 'html')
    app.add_config_value('needs_need_name', "Need", 'html')
    app.add_config_value('needs_spec_name', "Specification", 'html')
    app.add_config_value('needs_id_prefix_needs', "", 'html')
    app.add_config_value('needs_id_prefix_specs', "", 'html')
    app.add_config_value('needs_id_length', 5, 'html')
    app.add_config_value('needs_specs_show_needlist', False, 'html')


    # Define nodes
    app.add_node(need,
                 html=(visit_need_node, depart_need_node),
                 latex=(visit_need_node, depart_need_node),
                 text=(visit_need_node, depart_need_node))
    app.add_node(needlist)

    app.add_node(spec,
                 html=(visit_need_node, depart_need_node),
                 latex=(visit_need_node, depart_need_node),
                 text=(visit_need_node, depart_need_node))
    app.add_node(speclist)

    # Define directives
    app.add_directive('need', NeedDirective)
    app.add_directive('needlist', NeedlistDirective)
    app.add_directive('spec', SpecDirective)
    app.add_directive('speclist', SpeclistDirective)

    # Make connections to events
    app.connect('env-purge-doc', purge_needs)
    app.connect('env-purge-doc', purge_specs)
    app.connect('doctree-resolved', process_need_nodes)
    app.connect('doctree-resolved', process_need_nodelists)
    app.connect('doctree-resolved', process_spec_nodes)
    app.connect('doctree-resolved', process_spec_nodelists)

    return {'version': '0.1'}  # identifies the version of our extension


class need(nodes.Admonition, nodes.Element):
    pass


class needlist(nodes.General, nodes.Element):
    pass


class spec(nodes.Admonition, nodes.Element):
    pass


class speclist(nodes.General, nodes.Element):
    pass


def visit_need_node(self, node):
    self.visit_admonition(node)


def depart_need_node(self, node):
    self.depart_admonition(node)


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
                   'hide': directives.flag,
                   'hide_tags': directives.flag,
                   'hide_status': directives.flag,
                   'tags': directives.unicode_code}

    final_argument_whitespace = True

    def run(self):
        #############################################################################################
        # Get environment
        #############################################################################################
        env = self.state.document.settings.env
        if not hasattr(env.app.config, "needs_need_name"):
            needs_name = "Need"
        else:
            needs_name = env.app.config.needs_need_name

        # Calculate target id, to be able to set a link back
        targetid = "need-%d" % env.new_serialno('need')
        targetnode = nodes.target('', '', ids=[targetid])

        # Get the id or generate a random string/hash string, which is hopefully unique
        # TODO: Check, if id was already given. If True, recalculate id
        # id = self.options.get("id", ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for
        #  _ in range(5)))
        id = self.options.get("id",
                              "%s%s" % (env.app.config.needs_id_prefix_needs,
                                        hashlib.sha1(self.arguments[0].encode("UTF-8")).hexdigest().upper()
                                        [:env.app.config.needs_id_length]))

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
        title_text = '%s **%s** (%s)' % (needs_name, name, id)

        ad = make_admonition(need, self.name, [title_text], self.options,
                             self.content, self.lineno, self.content_offset,
                             self.block_text, self.state, self.state_machine)

        if status is not None and not hide_status:
            meta_line = nodes.line()
            meta_line += nodes.Text("status: ", "status: ")
            meta_line += nodes.strong(status, status)
            ad[0] += meta_line

        if len(tags) > 0 and not hide_tags:
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
            env.need_all_needs = {}

        # Add the need and all needed information
        env.need_all_needs[id] = {
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
        }

        if hide:
            return []

        return [targetnode] + ad


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


#####################################################################################################
# SPECS
#####################################################################################################
class SpecDirective(Directive):
    # this enables content in the directive
    has_content = True

    required_arguments = 1
    optional_arguments = 0
    option_spec = {'id': directives.unicode_code,
                   'status': directives.unicode_code,
                   'hide': directives.flag,
                   'hide_tags': directives.flag,
                   'hide_status': directives.flag,
                   'hide_needs': directives.flag,
                   'tags': directives.unicode_code,
                   'needs': directives.unicode_code,
                   'show_needlist': directives.flag}

    final_argument_whitespace = True

    def run(self):
        #############################################################################################
        # Get environment
        #############################################################################################
        env = self.state.document.settings.env
        if not hasattr(env.app.config, "spec_name"):
            spec_name = "Specification"
        else:
            spec_name = env.app.config.spec_name

        # Calculate target id, to be able to set a link back
        targetid = "spec-%d" % env.new_serialno('spec')
        targetnode = nodes.target('', '', ids=[targetid])

        # Get the id or generate a random string/hash string, which is hopefully unique
        # TODO: Check, if id was already given. If True, recalculate id
        # id = self.options.get("id", ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for
        #  _ in range(5)))
        id = self.options.get("id",
                              "%s%s" % (env.app.config.needs_id_prefix_specs,
                                        hashlib.sha1(self.arguments[0].encode("UTF-8")).hexdigest().upper()
                                        [:env.app.config.needs_id_length]))

        hide = True if "hide" in self.options.keys() else False
        hide_tags = True if "hide_tags" in self.options.keys() else False
        hide_status = True if "hide_status" in self.options.keys() else False
        hide_needs = True if "hide_needs" in self.options.keys() else False
        name = self.arguments[0]
        status = self.options.get("status", None)
        tags = self.options.get("tags", [])
        if len(tags) > 0:
            tags = [tag.strip() for tag in tags.split(";")]
        needs = self.options.get("needs", [])
        if len(needs) > 0:
            needs = [need.strip() for need in needs.split(";")]

        show_needlist = True if "show_needlist" in self.options.keys() else False

        # #############################################################################################
        # # Define Layout of a need
        # #############################################################################################
        title_text = '%s **%s** (%s)' % (spec_name, name, id)

        ad = make_admonition(spec, self.name, [title_text], self.options,
                             self.content, self.lineno, self.content_offset,
                             self.block_text, self.state, self.state_machine)

        if status is not None and not hide_status:
            meta_line = nodes.line()
            meta_line += nodes.Text("status: ", "status: ")
            meta_line += nodes.strong(status, status)
            ad[0] += meta_line

        if len(tags) > 0 and not hide_tags:
            meta_line = nodes.line()
            meta_line += nodes.Text(" tags: ", " tags: ")
            tag_text = "; ".join(tags)
            meta_line += nodes.strong(tag_text, tag_text)
            ad[0] += meta_line

        #############################################################################################
        # Add spec to global spec list
        #############################################################################################
        # be sure, global var is available. If not, create it
        if not hasattr(env, 'need_all_specs'):
            env.need_all_specs = {}

        # Add the need and all needed information
        env.need_all_specs[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'spec': ad[0],
            'target': targetnode,
            'status': status,
            'tags': tags,
            'needs': needs,
            'id': id,
            'name': name,
            'hide': hide,
            'hide_tags': hide_tags,
            'hide_status': hide_status,
            'hide_needs': hide_needs,
            'show_needlist': show_needlist
        }

        if hide:
            return []

        return [targetnode] + ad


class SpeclistDirective(Directive):
    def sort_by(argument):
        return directives.choice(argument, ("status", "id"))

    option_spec = {'status': directives.unicode_code,
                   'tags': directives.unicode_code,
                   'needs': directives.unicode_code,
                   'show_status': directives.flag,
                   'show_tags': directives.flag,
                   'show_needs': directives.flag,
                   'show_filters': directives.flag,
                   'sort_by': sort_by}

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_speclists'):
            env.need_all_speclists = {}

        targetid = "spec-%d" % env.new_serialno('spec')
        targetnode = nodes.target('', '', ids=[targetid])

        tags = self.options.get("tags", [])
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(";")]

        status = self.options.get("status", [])
        if isinstance(status, str):
            status = [stat.strip() for stat in status.split(";")]

        needs = self.options.get("needs", [])
        if isinstance(needs, str):
            needs = [need.strip() for need in needs.split(";")]

        # Add the spec and all needed information
        env.need_all_speclists[targetid] = {
            'status': status,
            'tags': tags,
            'needs': needs,
            'show_tags': True if self.options.get("show_tags", False) is None else False,
            'show_status': True if self.options.get("show_status", False) is None else False,
            'show_filters': True if self.options.get("show_filters", False) is None else False,
            'show_needs': True if self.options.get("show_needs", False) is None else False,
            'sort_by': self.options.get("sort_by", None)
        }

        return [targetnode] + [speclist('')]


def purge_needs(app, env, docname):
    if not hasattr(env, 'need_all_needs'):
        return
    env.need_all_needs = {key: need for key, need in env.need_all_needs.items() if need['docname'] != docname}


def purge_specs(app, env, docname):
    if not hasattr(env, 'need_all_specs'):
        return
    env.need_all_specs = [spec for spec in env.need_all_specs if spec['docname'] != docname]


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


def process_spec_nodes(app, doctree, fromdocname):
    if not app.config.needs_include_specs:
        for node in doctree.traverse(spec):
            node.parent.remove(node)


def process_spec_nodelists(app, doctree, fromdocname):
    # Replace all speclist nodes with a list of the collected specs.
    # Augment each spec with a backlink to the original location.
    env = app.builder.env

    for node in doctree.traverse(speclist):
        if not app.config.needs_include_specs:
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
        nodelist = env.need_all_speclists[id]

        all_specs = env.need_all_specs

        if nodelist["sort_by"] is not None:
            if nodelist["sort_by"] == "id":
                all_specs = sorted(all_specs, key=lambda node: node["id"])
            elif nodelist["sort_by"] == "status":
                all_specs = sorted(all_specs, key=status_sorter)

        for key, spec_info in all_specs.items():
            status_filter_passed = False
            if spec_info["status"] in nodelist["status"] or len(nodelist["status"]) == 0:
                status_filter_passed = True

            tags_filter_passed = False
            if len(set(spec_info["tags"]) & set(nodelist["tags"])) > 0 or len(nodelist["tags"]) == 0:
                tags_filter_passed = True

            needs_filter_passed = False
            if len(set(spec_info["needs"]) & set(nodelist["needs"])) > 0 or len(nodelist["needs"]) == 0:
                needs_filter_passed = True

            if status_filter_passed and tags_filter_passed and needs_filter_passed:
                para = nodes.line()
                description = "%s: %s" % (spec_info["id"], spec_info["name"])

                if nodelist["show_status"] and spec_info["status"] is not None:
                    description += " (%s)" % spec_info["status"]

                if nodelist["show_tags"] and spec_info["tags"] is not None:
                    description += " [%s]" % "; ".join(spec_info["tags"])

                title = nodes.Text(description, description)

                # Create a reference
                if not spec_info["hide"]:
                    ref = nodes.reference('', '')
                    ref['refdocname'] = spec_info['docname']
                    ref['refuri'] = app.builder.get_relative_uri(
                        fromdocname, spec_info['docname'])
                    ref['refuri'] += '#' + spec_info['target']['refid']
                    ref.append(title)
                    para += ref
                else:
                    para += title

                content.append(para)

        if len(content) == 0:
            nothing_found = "No specs passed the filters"
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

            if len(nodelist["needs"]) > 0 and (len(nodelist["status"]) > 0 or len(nodelist["tags"]) > 0):
                filter_text += " AND "
            filter_text += " needs(%s)" % " OR ".join(nodelist["needs"]) if len(nodelist["needs"]) > 0 else ""

            filter_node = nodes.emphasis(filter_text, filter_text)
            para += filter_node
            content.append(para)

        node.replace_self(content)


def process_spec_nodes(app, doctree, fromdocname):
    # Specs are showing the linked needs. We need so set a backref link for this needs.

    env = app.builder.env
    all_specs = env.need_all_specs

    for spec_node in doctree.traverse(spec):
        content = []
        id = spec_node.attributes["ids"][0]
        spec_obj = env.need_all_specs[id]
        if spec_obj["hide_needs"]:
            continue
        #############################################################################################
        # Define Layout of a need
        #############################################################################################
        all_needs = env.need_all_needs
        if len(spec_obj["needs"]) > 0:
            meta_line = nodes.line()
            meta_line += nodes.Text(" needs: ", " needs: ")

            for index, need in enumerate(spec_obj["needs"]):
                try:
                    need_node = all_needs[need]
                except KeyError:
                    print("WARNING: Need %s not found for spec %s" % (need, id))
                    continue
                ref = nodes.reference('', '')
                ref['refdocname'] = need_node['docname']
                ref['refuri'] = app.builder.get_relative_uri(
                    fromdocname, need_node['docname'])
                ref['refuri'] += '#' + need_node['target']['refid']

                if not spec_obj["show_needlist"] and not app.config.needs_specs_show_needlist:
                    title = nodes.Text(need, need)
                    ref.append(title)
                    meta_line += ref
                    if index < len(spec_obj["needs"]) - 1:
                        meta_line += nodes.Text("; ", "; ")
                else:
                    text = "%s: %s" % (need, need_node["name"])
                    title = nodes.Text(text, text)
                    line = nodes.line()
                    line += title
                    ref.append(line)
                    meta_line += ref

            spec_obj["spec"] += meta_line

        # node.replace_self([spec_obj["target"]] + spec_obj["spec"])
        spec_node.replace_self([spec_obj["target"], spec_obj["spec"]])


def status_sorter(a):
    """
    Helper function to sort string elements, which can be None, too.
    :param a: element, which gets sorted
    :return:
    """
    if not a["status"]:
        return ""
    return a["status"]
