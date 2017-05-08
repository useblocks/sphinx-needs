import hashlib
from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst import Directive
from jinja2 import Template
import os
from sphinx.roles import XRefRole
from sphinx.environment import NoUri
from sphinx.util.nodes import make_refnode
from sphinx.errors import SphinxError
import urllib

DEFAULT_TEMPLATE = """
.. _{{id}}:

{% if hide == false -%}
{{type_name}}: **{{title}}** ({{id}})

    {{content|indent(4) }}

    {% if status and not hide_status -%}
    **status**: {{status}}
    {% endif %}

    {% if tags and not hide_tags -%}
    **tags**: {{"; ".join(tags)}}
    {% endif %}

    {% if links -%}
    **links**:
    {% for link in links -%}
        :ref:`{{link}} <{{link}}>` {%if loop.index < links|length -%}; {% endif -%}
    {% endfor -%}
    {% endif -%}
{% endif -%}
"""

DEFAULT_DIAGRAM_TEMPLATE = "<size:12>{{type_name}}</size>\\n**{{title|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id}}</size>"


def setup(app):
    app.add_config_value('needs_types',
                         [dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
                          dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
                          dict(directive="impl", title="Implementation", prefix="I_", color="#DF744A", style="node"),
                          dict(directive="test", title="Test Case", prefix="T_", color="#DCB239", style="node"),
                          # Kept for backwards compatibility
                          dict(directive="need", title="Need", prefix="N_", color="#9856a5", style="node")
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
    app.add_config_value('needs_id_required', False, 'html')

    app.add_config_value('needs_diagram_template',
                         DEFAULT_DIAGRAM_TEMPLATE,
                         'html')

    # Define nodes
    app.add_node(need)
    app.add_node(needfilter)

    # Define directives
    # As values from conf.py are not available during setup phase, we have to import and read them by our own.
    # Otherwise this "app.config.needs_types" would always return the default values only.
    try:
        import imp
        config = imp.load_source("needs.app_conf", os.path.join(app.confdir, "conf.py"))
        types = getattr(config, "needs_types", app.config.needs_types)
    except Exception as e:
        types = app.config.needs_types

    for type in types:
        # Register requested types of needs
        app.add_directive( type["directive"], NeedDirective)
        app.add_directive("{0}_list".format(type["directive"]), NeedDirective)

    app.add_role('need', XRefRole(nodeclass=need_ref,
                                  innernodeclass=nodes.emphasis,
                                  warn_dangling=True))

    app.add_directive('needfilter', NeedfilterDirective)

    # Kept for backwards compatibility
    app.add_directive('needlist', NeedfilterDirective)

    # Make connections to events
    app.connect('env-purge-doc', purge_needs)
    app.connect('doctree-resolved', process_need_nodes)
    app.connect('doctree-resolved', process_needfilters)
    app.connect('doctree-resolved', process_need_refs)

    # Allows jinja statements in rst files
    # app.connect("source-read", rstjinja)

    return {'version': '0.1'}  # identifies the version of our extension


class need(nodes.General, nodes.Element):
    pass


class needfilter(nodes.General, nodes.Element):
    pass


class need_ref(nodes.Inline, nodes.Element):
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


class NeedfilterDirective(Directive):
    def sort_by(argument):
        return directives.choice(argument, ("status", "id"))

    def layout(argument):
        return directives.choice(argument, ("list", "table", "diagram"))

    option_spec = {'status': directives.unicode_code,
                   'tags': directives.unicode_code,
                   'types': directives.unicode_code,
                   'show_status': directives.flag,
                   'show_tags': directives.flag,
                   'show_filters': directives.flag,
                   'show_links': directives.flag,
                   'show_legend': directives.flag,
                   'sort_by': sort_by,
                   'layout': layout}

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_needlists'):
            env.need_all_needlists = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, 'need_all_needs'):
            env.need_all_needs = {}

        targetid = "needfilter-{docname}-{id}".format(
            docname=env.docname,
            id=env.new_serialno('needfilter'))
        targetnode = nodes.target('', '', ids=[targetid])

        tags = self.options.get("tags", [])
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(";")]

        status = self.options.get("status", [])
        if isinstance(status, str):
            status = [stat.strip() for stat in status.split(";")]

        types = self.options.get("types", [])
        if isinstance(types, str):
            types = [typ.strip() for typ in types.split(";")]

        # Add the need and all needed information
        env.need_all_needlists[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target': targetnode,
            'status': status,
            'tags': tags,
            'types': types,
            'show_tags': True if self.options.get("show_tags", False) is None else False,
            'show_status': True if self.options.get("show_status", False) is None else False,
            'show_filters': True if self.options.get("show_filters", False) is None else False,
            'show_legend': True if self.options.get("show_legend", False) is None else False,
            'sort_by': self.options.get("sort_by", None),
            'layout': self.options.get("layout", "list"),
        }

        return [targetnode] + [needfilter('')]


def purge_needs(app, env, docname):
    if not hasattr(env, 'need_all_needs'):
        return
    env.need_all_needs = {key: need for key, need in env.need_all_needs.items() if need['docname'] != docname}


def process_need_nodes(app, doctree, fromdocname):
    if not app.config.needs_include_needs:
        for node in doctree.traverse(need):
            node.parent.remove(node)


def process_needfilters(app, doctree, fromdocname):
    # Replace all needlist nodes with a list of the collected needs.
    # Augment each need with a backlink to the original location.
    env = app.builder.env

    # NEEDFILTER
    for node in doctree.traverse(needfilter):
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

        id = node.attributes["ids"][0]
        current_needlist = env.need_all_needlists[id]
        all_needs = env.need_all_needs

        if current_needlist["layout"] == "list":
            content = []

        elif current_needlist["layout"] == "diagram":
            content = []
            try:
                if "sphinxcontrib.plantuml" not in app.config.extensions:
                    raise ImportError
                from sphinxcontrib.plantuml import plantuml
            except ImportError:
                content = nodes.error()
                para = nodes.paragraph()
                text = nodes.Text("PlantUML is not available!", "PlantUML is not available!")
                para += text
                content.append(para)
                node.replace_self(content)
                continue

            plantuml_block_text = ".. plantuml::\n" \
                                  "\n" \
                                  "   @startuml" \
                                  "   @enduml"
            puml_node = plantuml(plantuml_block_text, **dict())
            puml_node["uml"] = "@startuml\n"
            puml_connections = ""

        elif current_needlist["layout"] == "table":
            content = nodes.table()
            tgroup = nodes.tgroup()
            id_colspec = nodes.colspec(colwidth=5)
            title_colspec = nodes.colspec(colwidth=15)
            type_colspec = nodes.colspec(colwidth=5)
            status_colspec = nodes.colspec(colwidth=5)
            links_colspec = nodes.colspec(colwidth=5)
            tags_colspec = nodes.colspec(colwidth=5)
            tgroup += [id_colspec, title_colspec, type_colspec, status_colspec, links_colspec, tags_colspec]
            tgroup += nodes.thead('', nodes.row(
                '',
                nodes.entry('', nodes.paragraph('', 'ID')),
                nodes.entry('', nodes.paragraph('', 'Title')),
                nodes.entry('', nodes.paragraph('', 'Type')),
                nodes.entry('', nodes.paragraph('', 'Status')),
                nodes.entry('', nodes.paragraph('', 'Links')),
                nodes.entry('', nodes.paragraph('', 'Tags'))
            ))
            tbody = nodes.tbody()
            tgroup += tbody
            content += tgroup

        all_needs = list(all_needs.values())
        if current_needlist["sort_by"] is not None:
            if current_needlist["sort_by"] == "id":
                all_needs = sorted(all_needs, key=lambda node: node["id"])
            elif current_needlist["sort_by"] == "status":
                all_needs = sorted(all_needs, key=status_sorter)

        for need_info in all_needs:
            status_filter_passed = False
            if need_info["status"] in current_needlist["status"] or len(current_needlist["status"]) == 0:
                status_filter_passed = True

            tags_filter_passed = False
            if len(set(need_info["tags"]) & set(current_needlist["tags"])) > 0 or len(current_needlist["tags"]) == 0:
                tags_filter_passed = True

            type_filter_passed = False
            if need_info["type"] in current_needlist["types"] \
                    or need_info["type_name"] in current_needlist["types"] \
                    or len(current_needlist["types"]) == 0:
                type_filter_passed = True

            if status_filter_passed and tags_filter_passed and type_filter_passed:
                if current_needlist["layout"] == "list":
                    para = nodes.line()
                    description = "%s: %s" % (need_info["id"], need_info["title"])

                    if current_needlist["show_status"] and need_info["status"] is not None:
                        description += " (%s)" % need_info["status"]

                    if current_needlist["show_tags"] and need_info["tags"] is not None:
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
                elif current_needlist["layout"] == "table":
                    row = nodes.row()
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "id", make_ref=True)
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "title")
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "type_name")
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "status")
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "links", ref_lookup=True)
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "tags")
                    tbody += row
                elif current_needlist["layout"] == "diagram":
                    # Link calculation
                    # All links we can get from docutils functions will be relative.
                    # But the generated link in the svg will be relative to the svg-file location
                    # (e.g. server.com/docs/_images/sqwxo499cnq329439dfjne.svg)
                    # and not to current documentation. Therefore we need to add ../ to get out of the _image folder.
                    try:
                        link = "../" + app.builder.get_target_uri(need_info['docname']) \
                               + "?highlight={0}".format(urllib.parse.quote_plus(need_info['title'])) \
                               + "#" \
                               + need_info['target']['refid'] \
                        # Gets mostly called during latex generation
                    except NoUri:
                        link = ""

                    diagram_template = Template(env.config.needs_diagram_template)
                    node_text = diagram_template.render(**need_info)

                    puml_node["uml"] += '{style} "{node_text}" as {id} [[{link}]] {color}\n'.format(
                        id=need_info["id"], node_text=node_text, link=link, color=need_info["type_color"],
                        style=need_info["type_style"])
                    for link in need_info["links"]:
                        puml_connections += '{id} --> {link}\n'.format(id=need_info["id"], link=link)

        if current_needlist["layout"] == "diagram":
            puml_node["uml"] += puml_connections

            # Create a legend

            if current_needlist["show_legend"]:
                puml_node["uml"] += "legend\n"
                puml_node["uml"] += "|= Color |= Type |\n"
                for need in app.config.needs_types:
                    puml_node["uml"] += "|<back:{color}> {color} </back>| {name} |\n".format(
                        color=need["color"], name=need["title"])
                puml_node["uml"] += "endlegend\n"
            puml_node["uml"] += "@enduml"
            puml_node["incdir"] = os.path.dirname(current_needlist["docname"])
            content.append(puml_node)

        if len(content) == 0:
            nothing_found = "No needs passed the filters"
            para = nodes.line()
            nothing_found_node = nodes.Text(nothing_found, nothing_found)
            para += nothing_found_node
            content.append(para)
        if current_needlist["show_filters"]:
            para = nodes.paragraph()
            filter_text = "Used filter:"
            filter_text += " status(%s)" % " OR ".join(current_needlist["status"]) if len(
                current_needlist["status"]) > 0 else ""
            if len(current_needlist["status"]) > 0 and len(current_needlist["tags"]) > 0:
                filter_text += " AND "
            filter_text += " tags(%s)" % " OR ".join(current_needlist["tags"]) if len(
                current_needlist["tags"]) > 0 else ""
            if (len(current_needlist["status"]) > 0 or len(current_needlist["tags"]) > 0) and len(
                    current_needlist["types"]) > 0:
                filter_text += " AND "
            filter_text += " types(%s)" % " OR ".join(current_needlist["types"]) if len(
                current_needlist["types"]) > 0 else ""

            filter_node = nodes.emphasis(filter_text, filter_text)
            para += filter_node
            content.append(para)

        node.replace_self(content)


def process_need_refs(app, doctree, fromdocname):
    for node_need_ref in doctree.traverse(need_ref):
        env = app.builder.env
        # Let's create a dummy node, for the case we will not be able to create a real reference
        new_node_ref = make_refnode(app.builder,
                                    fromdocname,
                                    fromdocname,
                                    'Unknown need',
                                    node_need_ref[0].deepcopy(),
                                    node_need_ref['reftarget'] + '?')

        # If need target exists, let's create the reference
        if node_need_ref['reftarget'].upper() in env.need_all_needs:
            target_need = env.need_all_needs[node_need_ref['reftarget'].upper()]
            try:
                link_text = "{title} ({id})".format(title=target_need["title"], id=target_need["id"])
                node_need_ref[0].children[0] = nodes.Text(link_text, link_text)

                new_node_ref = make_refnode(app.builder,
                                            fromdocname,
                                            target_need['docname'],
                                            target_need['target']['refid'],
                                            node_need_ref[0].deepcopy(),
                                            node_need_ref['reftarget'].upper())
            except NoUri:
                # Irf the given need id can not be found, we must pass here....
                pass

        else:
            env.warn_node(
                'Needs: need %s not found' % node_need_ref['reftarget'], node_need_ref)

        node_need_ref.replace_self(new_node_ref)


def row_col_maker(app, fromdocname, all_needs, need_info, need_key, make_ref=False, ref_lookup=False):
    """
    Creates and returns a column.

    :param app: current sphinx app
    :param fromdocname: current document
    :param all_needs: Dictionary of all need objects
    :param need_info: need_info object, which stores all related need data
    :param need_key: The key to access the needed data from need_info
    :param make_ref: If true, creates a reference for the given data in need_key
    :param ref_lookup: If true, it uses the data to lookup for a related need and uses its data to create the reference
    :return: column object (nodes.entry)
    """
    row_col = nodes.entry()
    para_col = nodes.paragraph()

    if need_info[need_key] is not None:
        if not isinstance(need_info[need_key], list):
            data = [need_info[need_key]]
        else:
            data = need_info[need_key]

        for index, datum in enumerate(data):
            text_col = nodes.Text(datum, datum)
            if make_ref or ref_lookup:
                try:
                    ref_col = nodes.reference("", "")
                    if not ref_lookup:
                        ref_col['refuri'] = app.builder.get_relative_uri(fromdocname, need_info['docname'])
                        ref_col['refuri'] += "#" + datum
                    else:
                        temp_need = all_needs[datum]
                        ref_col['refuri'] = app.builder.get_relative_uri(fromdocname, temp_need['docname'])
                        ref_col['refuri'] += "#" + temp_need["id"]

                except KeyError:
                    para_col += text_col
                else:
                    ref_col.append(text_col)
                    para_col += ref_col
            else:
                para_col += text_col

            if index + 1 < len(data):
                para_col += nodes.emphasis("; ", "; ")

        row_col += para_col
    return row_col


def status_sorter(a):
    """
    Helper function to sort string elements, which can be None, too.
    :param a: element, which gets sorted
    :return:
    """
    if not a["status"]:
        return ""
    return a["status"]


def rstjinja(app, docname, source):
    """
    Render our pages as a jinja template for fancy templating goodness.
    """
    # Make sure we're outputting HTML
    if app.builder.format != 'html':
        return
    src = source[0]
    rendered = app.builder.templates.render_string(
        src, app.config.html_context
    )
    source[0] = rendered


class NeedsNoIdException(SphinxError):
    pass
