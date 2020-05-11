import os

import sphinx
import sys
import urllib

from docutils import nodes
from docutils.parsers.rst import directives
from jinja2 import Template
from pkg_resources import parse_version

from sphinxcontrib.needs.diagrams_common import DiagramBase, make_entity_name, no_plantuml, \
    add_config, get_filter_para, get_debug_containter

from sphinxcontrib.plantuml import generate_name  # Need for plantuml filename calculation

try:
    from sphinx.errors import NoUri  # Sphinx 3.0
except ImportError:
    from sphinx.environment import NoUri  # Sphinx < 3.0

from sphinxcontrib.needs.filter_common import FilterBase, procces_filters, filter_single_need

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


class Needsequence(nodes.General, nodes.Element):
    pass


class NeedsequenceDirective(FilterBase, DiagramBase):
    """
    Directive to get sequence diagrams.
    """
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {}

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self):
        env = self.state.document.settings.env
        # Creates env.need_all_needsequences safely and other vars
        self.prepare_env('needsequences')

        id, targetid, targetnode = self.create_target('needsequence')

        # Add the needsequence and all needed information
        env.need_all_needsequences[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target_node': targetnode,
            'env': env
        }
        # Data for filtering
        env.need_all_needsequences[targetid].update(self.collect_filter_attributes())
        # Data for diagrams
        env.need_all_needsequences[targetid].update(self.collect_diagram_attributes())

        return [targetnode] + [Needsequence('')]


def process_needsequence(app, doctree, fromdocname):
    # Replace all needsequence nodes with a list of the collected needs.
    env = app.builder.env

    link_types = env.config.needs_extra_links
    allowed_link_types_options = [link.upper() for link in env.config.needs_flow_link_types]

    # NEEDSEQUENCE
    for node in doctree.traverse(NeedsequenceDirective):
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
        current_needsequence = env.need_all_needsequences[id]
        all_needs = env.needs_all_needs

        option_link_types = [link.upper() for link in current_needsequence['link_types']]
        for lt in option_link_types:
            if lt not in [link['option'].upper() for link in link_types]:
                logger.warning('Unknown link type {link_type} in needsequence {flow}. Allowed values:'
                               ' {link_types}'.format(link_type=lt, flow=current_needsequence['target_node'],
                                                      link_types=",".join(link_types)
                                                      ))

        content = []
        try:
            if "sphinxcontrib.plantuml" not in app.config.extensions:
                raise ImportError
            from sphinxcontrib.plantuml import plantuml
        except ImportError:
            no_plantuml(node)
            continue

        plantuml_block_text = ".. plantuml::\n" \
                              "\n" \
                              "   @startuml" \
                              "   @enduml"
        puml_node = plantuml(plantuml_block_text, **dict())
        puml_node["uml"] = "@startuml\n"
        puml_connections = ""

        # Adding config
        config = current_needsequence['config']
        puml_node["uml"] += add_config(config)

        all_needs = list(all_needs.values())
        found_needs = procces_filters(all_needs, current_needsequence)

        processed_need_part_ids = []

        puml_node["uml"] += '\n\' Nodes definition \n\n'

        for need_info in found_needs:
            pass

        puml_node["uml"] += '\n\' Connection definition \n\n'


        # Create a legend
        if current_needsequence["show_legend"]:
            puml_node["uml"] += '\n\n\' Legend definition \n\n'

            puml_node["uml"] += "legend\n"
            puml_node["uml"] += "|= Color |= Type |\n"
            for need in app.config.needs_types:
                puml_node["uml"] += "|<back:{color}> {color} </back>| {name} |\n".format(
                    color=need["color"], name=need["title"])
            puml_node["uml"] += "endlegend\n"

        puml_node["uml"] += "\n@enduml"
        puml_node["incdir"] = os.path.dirname(current_needsequence["docname"])
        puml_node["filename"] = os.path.split(current_needsequence["docname"])[1]  # Needed for plantuml >= 0.9

        scale = int(current_needsequence['scale'])
        # if scale != 100:
        puml_node['scale'] = scale

        puml_node = nodes.figure('', puml_node)

        if current_needsequence['align'] is not None and len(current_needsequence['align']) != '':
            puml_node['align'] = current_needsequence['align']
        else:
            puml_node['align'] = 'center'

        if current_needsequence['caption'] is not None and len(current_needsequence['caption']) != '':
            # Make the caption to a link to the original file.
            try:
                if "SVG" in app.config.plantuml_output_format.upper():
                    file_ext = 'svg'
                else:
                    file_ext = 'png'
            except Exception:
                file_ext = 'png'

            gen_flow_link = generate_name(app, puml_node.children[0], file_ext)
            current_file_parts = fromdocname.split('/')
            subfolder_amount = len(current_file_parts) - 1
            img_locaton = '../' * subfolder_amount + '_images/' + gen_flow_link[0].split('/')[-1]
            flow_ref = nodes.reference('t', current_needsequence['caption'], refuri=img_locaton)
            puml_node += nodes.caption('', '', flow_ref)

        content.append(puml_node)

        if len(content) == 0:
            nothing_found = "No needs passed the filters"
            para = nodes.paragraph()
            nothing_found_node = nodes.Text(nothing_found, nothing_found)
            para += nothing_found_node
            content.append(para)
        if current_needsequence["show_filters"]:
            content.append(get_filter_para(current_needsequence))

        if current_needsequence['debug']:
            content += get_debug_containter(puml_node)

        node.replace_self(content)
