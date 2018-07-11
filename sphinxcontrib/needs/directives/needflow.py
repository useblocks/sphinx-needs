import os
import sys
import urllib

from docutils import nodes
from docutils.parsers.rst import directives
from jinja2 import Template
from sphinx.environment import NoUri
from sphinxcontrib.needs.utils import status_sorter

from sphinxcontrib.needs.filter_base import FilterBase, procces_filters

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
                   'show_filters': directives.flag}

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_needflows'):
            env.need_all_needflows = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, 'need_all_needs'):
            env.need_all_needs = {}

        targetid = "needflow-{docname}-{id}".format(
            docname=env.docname,
            id=env.new_serialno('needflow'))
        targetnode = nodes.target('', '', ids=[targetid])

        # Add the need and all needed information
        env.need_all_needflows[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target_node': targetnode,
            'show_filters': True if self.options.get("show_filters", False) is None else False,
            'show_legend': True if self.options.get("show_legend", False) is None else False,
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
        all_needs = env.need_all_needs

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

        if current_needflow["sort_by"] is not None:
            if current_needflow["sort_by"] == "id":
                all_needs = sorted(all_needs, key=lambda node: node["id"])
            elif current_needflow["sort_by"] == "status":
                all_needs = sorted(all_needs, key=status_sorter)

        found_needs = procces_filters(all_needs, current_needflow)

        for need_info in found_needs:
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

            diagram_template = Template(env.config.needs_diagram_template)
            node_text = diagram_template.render(**need_info)

            puml_node["uml"] += '{style} "{node_text}" as {id} [[{link}]] {color}\n'.format(
                id=make_entity_name(need_info["id"]), node_text=node_text,
                link=make_entity_name(link), color=need_info["type_color"],
                style=need_info["type_style"])
            for link in need_info["links"]:
                puml_connections += '{id} --> {link}\n'.format(
                    id=make_entity_name(need_info["id"]),
                    link=make_entity_name(link)
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
            para = nodes.line()
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
