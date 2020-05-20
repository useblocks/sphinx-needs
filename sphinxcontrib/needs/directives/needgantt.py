import os
import re
import sphinx
import sys
import urllib

from datetime import datetime
from docutils import nodes
from docutils.parsers.rst import directives
from pkg_resources import parse_version


from sphinxcontrib.needs.diagrams_common import DiagramBase, no_plantuml, \
    add_config, get_filter_para, get_debug_containter, calculate_link
from sphinxcontrib.needs.utils import MONTH_NAMES

from sphinxcontrib.plantuml import generate_name  # Need for plantuml filename calculation

try:
    from sphinx.errors import NoUri  # Sphinx 3.0
except ImportError:
    from sphinx.environment import NoUri  # Sphinx < 3.0

from sphinxcontrib.needs.filter_common import FilterBase, procces_filters, filter_single_need
from sphinxcontrib.needs.directives.utils import get_link_type_option

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


class Needgantt(nodes.General, nodes.Element):
    pass


class NeedganttDirective(FilterBase, DiagramBase):
    """
    Directive to get gantt diagrams.
    """
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        'starts_with_links': directives.unchanged,
        'starts_after_links': directives.unchanged,
        'ends_with_links': directives.unchanged,
        'milestone_filter': directives.unchanged,
        'start_date': directives.unchanged,
        'timeline': directives.unchanged,
        'duration_option': directives.unchanged,
        'completion_option': directives.unchanged,
        'no_color': directives.flag,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)
    option_spec.update(DiagramBase.base_option_spec)

    def run(self):
        env = self.state.document.settings.env
        # Creates env.need_all_needgantts safely and other vars
        self.prepare_env('needgantts')

        id, targetid, targetnode = self.create_target('needgantt')

        starts_with_links = get_link_type_option('starts_with_links', env, self, '')
        starts_after_links = get_link_type_option('starts_after_links', env, self, 'links')
        ends_with_links = get_link_type_option('ends_with_links', env, self)

        milestone_filter = self.options.get('milestone_filter', None)
        start_date = self.options.get('start_date', None)
        if start_date is not None and start_date != '':
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                # datetime.fromisoformat(start_date) # > py3.7 only
            except Exception:
                raise NeedGanttException('Given start date {} is not valid. Please use YYYY-MM-DD as format. '
                                         'E.g. 2020-03-27'.format(start_date))
        else:
            start_date = None  # If None we do not set a start date later

        timeline = self.options.get('timeline', None)
        timeline_options = ['daily', 'weekly', 'monthly']
        if timeline is not None and timeline != '':
            if timeline not in timeline_options:
                raise NeedGanttException('Given scale value {} is invalid. Please use: '
                                         '{}'.format(timeline, ",".join(timeline_options)))
        else:
            timeline = None  # Timeline/scale not set later

        no_color = True if "no_color" in self.options.keys() else False

        duration_option = self.options.get('duration_option', env.app.config.needs_duration_option)
        completion_option = self.options.get('completion_option', env.app.config.needs_completion_option)

        # Add the needgantt and all needed information
        env.need_all_needgantts[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target_node': targetnode,
            'env': env,
            'starts_with_links': starts_with_links,
            'starts_after_links': starts_after_links,
            'ends_with_links': ends_with_links,
            'milestone_filter': milestone_filter,
            'start_date': start_date,
            'timeline': timeline,
            'no_color': no_color,
            'duration_option': duration_option,
            'completion_option': completion_option
        }
        # Data for filtering
        env.need_all_needgantts[targetid].update(self.collect_filter_attributes())
        # Data for diagrams
        env.need_all_needgantts[targetid].update(self.collect_diagram_attributes())

        return [targetnode] + [Needgantt('')]


def process_needgantt(app, doctree, fromdocname):
    # Replace all needgantt nodes with a list of the collected needs.
    env = app.builder.env

    link_types = env.config.needs_extra_links
    allowed_link_types_options = [link.upper() for link in env.config.needs_flow_link_types]

    # NEEDGANTT
    for node in doctree.traverse(Needgantt):
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
        current_needgantt = env.need_all_needgantts[id]
        all_needs_dict = env.needs_all_needs

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
        config = current_needgantt['config']
        puml_node["uml"] += add_config(config)

        all_needs = list(all_needs_dict.values())
        found_needs = procces_filters(all_needs, current_needgantt)

        # Scale/timeline handling
        if current_needgantt['timeline'] is not None and current_needgantt['timeline'] != '':
            puml_node["uml"] += 'printscale {}\n'.format(current_needgantt["timeline"])

        # Project start date handling
        start_date_string = current_needgantt['start_date']
        start_date_plantuml = None
        if start_date_string is not None and start_date_string != '':
            try:
                start_date = datetime.strptime(start_date_string, '%Y-%m-%d')
                # start_date = datetime.fromisoformat(start_date_string)  # > py3.7 only
            except Exception:
                raise NeedGanttException('start_date "{}"for needgantt is invalid. '
                                         'File: {}:current_needgantt["lineno"]'.format(
                    start_date_string, current_needgantt["docname"]
                ))

            month = MONTH_NAMES[int(start_date.strftime("%-m"))]
            start_date_plantuml = start_date.strftime("%dth of {} %Y".format(month))
        if start_date_plantuml is not None:
            puml_node["uml"] += 'Project starts the {}\n'.format(start_date_plantuml)

        # Element handling
        puml_node["uml"] += '\n\' Elements definition \n\n'
        el_link_string = ''
        el_completion_string = ''
        el_color_string = ''
        for need in found_needs:
            complete = None

            if current_needgantt['milestone_filter'] is None or current_needgantt['milestone_filter'] == '':
                is_milestone = False
            else:
                is_milestone = filter_single_need(need, current_needgantt['milestone_filter'])
            if current_needgantt['milestone_filter'] is None or current_needgantt['milestone_filter'] == '' or \
                    not is_milestone:
                # Normal gantt element handling
                duration_option = current_needgantt['duration_option']
                duration = need[duration_option]
                complete_option = current_needgantt['completion_option']
                complete = need[complete_option]
                if duration is None or duration == '' or not duration.isdigit():
                    logger.warning('Duration not set or invalid for needgantt chart. '
                                   'Need: {}. Duration: {}'.format(need["id"], duration))
                    duration = 1
                gantt_element = '[{}] as [{}] lasts {} days\n'.format(need["title"], need["id"], duration)
            else:
                gantt_element = '[{}] as [{}] lasts 0 days\n'.format(need["title"], need["id"])

            el_link_string += '[{}] links to [[{}]]\n'.format(need["title"], calculate_link(app, need))

            if complete is not None and complete != '':
                complete = complete.replace('%', '')
                el_completion_string += '[{}] is {}% completed\n'.format(need["title"], complete)

            el_color_string += '[{}] is colored in {}\n'.format(need["title"], need["type_color"])

            puml_node["uml"] += gantt_element

        puml_node["uml"] += '\n\' Element links definition \n\n'
        puml_node["uml"] += '\n\' Deactivated, as currently supported by plantuml beta only'
        # ToDo: Activate if linking is working with default plantuml
        # puml_node["uml"] += el_link_string + '\n'

        puml_node["uml"] += '\n\' Element completion definition \n\n'
        puml_node["uml"] += el_completion_string + '\n'

        puml_node["uml"] += '\n\' Element color definition \n\n'
        if current_needgantt['no_color']:
            puml_node["uml"] += '\' Color support deactivated via flag'
        else:
            puml_node["uml"] += el_color_string + '\n'

        # Constrain handling
        puml_node["uml"] += '\n\' Constraints definition \n\n'
        puml_node["uml"] += '\n\' Constraints definition \n\n'
        for need in found_needs:
            if current_needgantt['milestone_filter'] is None or current_needgantt['milestone_filter'] == '':
                is_milestone = False
            else:
                is_milestone = filter_single_need(need, current_needgantt['milestone_filter'])
            constrain_types = ['starts_with_links', 'starts_after_links', 'ends_with_links']
            for con_type in constrain_types:
                if is_milestone:
                    keyword = 'happens'
                elif con_type in ['starts_with_links', 'starts_after_links']:
                    keyword = 'starts'
                else:
                    keyword = 'ends'

                if con_type in ['starts_after_links', 'ends_with_links']:
                    start_end_sync = 'end'
                else:
                    start_end_sync = 'start'

                for link_type in current_needgantt[con_type]:
                    start_with_links = need[link_type]
                    for start_with_link in start_with_links:
                        start_need = all_needs_dict[start_with_link]
                        gantt_constraint = '[{}] {} at [{}]\'s ' \
                                           '{}\n'.format(need["id"], keyword, start_need["id"], start_end_sync)
                        puml_node["uml"] += gantt_constraint

        # Create a legend
        if current_needgantt["show_legend"]:
            puml_node["uml"] += '\n\n\' Legend definition \n\n'

            puml_node["uml"] += "legend\n"
            puml_node["uml"] += "|= Color |= Type |\n"
            for need in app.config.needs_types:
                puml_node["uml"] += "|<back:{color}> {color} </back>| {name} |\n".format(
                    color=need["color"], name=need["title"])
            puml_node["uml"] += "endlegend\n"

        puml_node["uml"] += "\n@enduml"
        puml_node["incdir"] = os.path.dirname(current_needgantt["docname"])
        puml_node["filename"] = os.path.split(current_needgantt["docname"])[1]  # Needed for plantuml >= 0.9

        scale = int(current_needgantt['scale'])
        # if scale != 100:
        puml_node['scale'] = scale

        puml_node = nodes.figure('', puml_node)

        if current_needgantt['align'] is not None and len(current_needgantt['align']) != '':
            puml_node['align'] = current_needgantt['align']
        else:
            puml_node['align'] = 'center'

        if current_needgantt['caption'] is not None and len(current_needgantt['caption']) != '':
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
            flow_ref = nodes.reference('t', current_needgantt['caption'], refuri=img_locaton)
            puml_node += nodes.caption('', '', flow_ref)

        content.append(puml_node)

        if len(content) == 0:
            nothing_found = "No needs passed the filters"
            para = nodes.paragraph()
            nothing_found_node = nodes.Text(nothing_found, nothing_found)
            para += nothing_found_node
            content.append(para)
        if current_needgantt["show_filters"]:
            content.append(get_filter_para(current_needgantt))

        if current_needgantt['debug']:
            content += get_debug_containter(puml_node)

        puml_node['class'] = ['needgantt']
        node.replace_self(content)


class NeedGanttException(BaseException):
    """Errors during Gantt handling"""
