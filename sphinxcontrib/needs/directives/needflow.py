import os
import re
import sphinx
import sys
import urllib

from docutils import nodes
from docutils.parsers.rst import directives
from jinja2 import Template
from pkg_resources import parse_version
from sphinx.environment import NoUri
from sphinxcontrib.needs.utils import status_sorter

from sphinxcontrib.needs.filter_common import FilterBase, procces_filters

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging
logger = logging.getLogger(__name__)

if sys.version_info.major < 3:
    urlParse = urllib.quote_plus
else:
    urlParse = urllib.parse.quote_plus


class Needflow(nodes.General, nodes.Element):
    pass


class NeedflowDirective(FilterBase):
    """
    Directive to filter needs and present them inside a list, table or diagram.

    .. deprecated:: 0.2.0
       Use needlist, needtable or needdiagram instead
    """
    option_spec = {'show_legend': directives.flag,
                   'show_filters': directives.flag,
                   'show_link_names': directives.flag,
                   'link_types': directives.unchanged_required}

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_needflows'):
            env.need_all_needflows = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, 'needs_all_needs'):
            env.needs_all_needs = {}

        id = env.new_serialno('needflow')
        targetid = "needflow-{docname}-{id}".format(
            docname=env.docname,
            id=id)
        targetnode = nodes.target('', '', ids=[targetid])

        link_types = self.options.get("link_types", [])
        if len(link_types) > 0:
            link_types = [link_type.strip() for link_type in re.split(";|,", link_types)]
            for i in range(len(link_types)):
                if len(link_types[i]) == 0 or link_types[i].isspace():
                    del (link_types[i])
                    logger.warning('Scruffy link_type definition found in needflow {}. '
                                   'Defined link_type contains spaces only.'.format(id))

        # Add the need and all needed information
        env.need_all_needflows[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target_node': targetnode,
            'show_filters': True if self.options.get("show_filters", False) is None else False,
            'show_legend': True if self.options.get("show_legend", False) is None else False,
            'show_link_names': True if self.options.get("show_link_names", False) is None else False,
            'link_types': link_types,
            'export_id': self.options.get("export_id", ""),
            'env': env
        }
        env.need_all_needflows[targetid].update(self.collect_filter_attributes())

        return [targetnode] + [Needflow('')]


def make_entity_name(name):
    """Creates a valid PlantUML entity name from the given value."""
    invalid_chars = "-=!#$%^&*[](){}/~'`<>:;"
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name


def process_needflow(app, doctree, fromdocname):
    # Replace all needflow nodes with a list of the collected needs.
    # Augment each need with a backlink to the original location.
    env = app.builder.env

    link_types = env.config.needs_extra_links
    allowed_link_types_options = [link.upper() for link in env.config.needs_flow_link_types]

    # NEEDFLOW
    for node in doctree.traverse(Needflow):
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
        current_needflow = env.need_all_needflows[id]
        all_needs = env.needs_all_needs

        option_link_types = [link.upper() for link in current_needflow['link_types']]
        for lt in option_link_types:
            if lt not in [link['option'].upper() for link in link_types]:
                logger.warning('Unknown link type {link_type} in needflow {flow}. Allowed values: {link_types}'.format(
                    link_type=lt, flow=current_needflow['target_node'], link_types=",".join(link_types)
                ))

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

        all_needs = list(all_needs.values())
        found_needs = procces_filters(all_needs, current_needflow)

        processed_need_part_ids = []

        for need_info in found_needs:
            # Check if need_part was already handled during handling of parent need.
            # If this is the case, it is already part of puml-code and we do not need to create a node.
            if not (need_info['is_part'] and need_info['id_complete'] in processed_need_part_ids):
                # Check if we need to embed need_parts into parent need, because they are also part of search result.
                node_part_code = ""
                valid_need_parts = [x for x in found_needs if x['is_part'] and x['id_parent'] == need_info['id']]
                for need_part in valid_need_parts:
                    part_link = calculate_link(app, need_part)
                    diagram_template = Template(env.config.needs_diagram_template)
                    part_text = diagram_template.render(**need_part)
                    node_part_code += '{style} "{node_text}" as {id} [[{link}]] {color}\n'.format(
                        id=make_entity_name(need_part["id_complete"]), node_text=part_text,
                        link=make_entity_name(part_link), color=need_part["type_color"],
                        style=need_part["type_style"])

                    processed_need_part_ids.append(need_part['id_complete'])

                link = calculate_link(app, need_info)

                diagram_template = Template(env.config.needs_diagram_template)
                node_text = diagram_template.render(**need_info)
                if need_info['is_part']:
                    need_id = need_info['id_complete']
                else:
                    need_id = need_info['id']
                node_code = '{style} "{node_text}" as {id} [[{link}]] {color} {{\n {need_parts} }}\n'.format(
                    id=make_entity_name(need_id), node_text=node_text,
                    link=make_entity_name(link), color=need_info["type_color"],
                    style=need_info["type_style"], need_parts=node_part_code)
                puml_node["uml"] += node_code

            for link_type in link_types:
                # Skip link-type handling, if it is not part of a specified list of allowed link_types or
                # if not part of the overall configuration of needs_flow_link_types
                if (current_needflow["link_types"] and link_type['option'].upper() not in option_link_types) or \
                        (not current_needflow["link_types"] and \
                         link_type['option'].upper() not in allowed_link_types_options):
                    continue

                for link in need_info[link_type['option']]:
                    if '.' in link:
                        # final_link = link.split('.')[0]
                        final_link = link
                        if current_needflow["show_link_names"] or env.config.needs_flow_show_links:
                            desc = link_type['outgoing'] + '\\n'
                        else:
                            desc = ''

                        comment = ': {desc}{part}'.format(desc=desc, part=link.split('.')[1])
                        if "style_part" in link_type.keys() and link_type['style_part'] is not None and \
                                len(link_type['style_part']) > 0:
                            link_style = '[{style}]'.format(style=link_type['style_part'])
                        else:
                            link_style = "[dotted]"
                    else:
                        final_link = link
                        if current_needflow["show_link_names"] or env.config.needs_flow_show_links:
                            comment = ': {desc}'.format(desc=link_type['outgoing'])
                        else:
                            comment = ''

                        if "style" in link_type.keys() and link_type['style'] is not None and \
                                len(link_type['style']) > 0:
                            link_style = '[{style}]'.format(style=link_type['style'])
                        else:
                            link_style = ""

                    # Do not create an links, if the link target is not part of the search result.
                    if final_link not in [x['id'] for x in found_needs if x['is_need']] and \
                            final_link not in [x['id_complete'] for x in found_needs if x['is_part']]:
                        continue

                    puml_connections += '{id} --{link_style}> {link}{comment}\n'.format(
                        id=make_entity_name(need_info["id"]),
                        link=make_entity_name(final_link),
                        comment=comment,
                        link_style=link_style
                    )

        puml_node["uml"] += puml_connections

        # Create a legend
        if current_needflow["show_legend"]:
            puml_node["uml"] += "legend\n"
            puml_node["uml"] += "|= Color |= Type |\n"
            for need in app.config.needs_types:
                puml_node["uml"] += "|<back:{color}> {color} </back>| {name} |\n".format(
                    color=need["color"], name=need["title"])
            puml_node["uml"] += "endlegend\n"
        puml_node["uml"] += "@enduml"
        puml_node["incdir"] = os.path.dirname(current_needflow["docname"])
        puml_node["filename"] = os.path.split(current_needflow["docname"])[1]  # Needed for plantuml >= 0.9
        content.append(puml_node)

        if len(content) == 0:
            nothing_found = "No needs passed the filters"
            para = nodes.paragraph()
            nothing_found_node = nodes.Text(nothing_found, nothing_found)
            para += nothing_found_node
            content.append(para)
        if current_needflow["show_filters"]:
            para = nodes.paragraph()
            filter_text = "Used filter:"
            filter_text += " status(%s)" % " OR ".join(current_needflow["status"]) if len(
                current_needflow["status"]) > 0 else ""
            if len(current_needflow["status"]) > 0 and len(current_needflow["tags"]) > 0:
                filter_text += " AND "
            filter_text += " tags(%s)" % " OR ".join(current_needflow["tags"]) if len(
                current_needflow["tags"]) > 0 else ""
            if (len(current_needflow["status"]) > 0 or len(current_needflow["tags"]) > 0) and len(
                    current_needflow["types"]) > 0:
                filter_text += " AND "
            filter_text += " types(%s)" % " OR ".join(current_needflow["types"]) if len(
                current_needflow["types"]) > 0 else ""

            filter_node = nodes.emphasis(filter_text, filter_text)
            para += filter_node
            content.append(para)
        node.replace_self(content)


def calculate_link(app, need_info):
    # Link calculation
    # All links we can get from docutils functions will be relative.
    # But the generated link in the svg will be relative to the svg-file location
    # (e.g. server.com/docs/_images/sqwxo499cnq329439dfjne.svg)
    # and not to current documentation. Therefore we need to add ../ to get out of the _image folder.
    try:
        link = "../" + app.builder.get_target_uri(need_info['docname']) \
               + "?highlight={0}".format(urlParse(need_info['title'])) \
               + "#" \
               + need_info['target_node']['refid'] \
            # Gets mostly called during latex generation
    except NoUri:
        link = ""

    return link
