"""


"""

import sys
import urllib

from docutils import nodes
from docutils.parsers.rst import directives

from sphinxcontrib.needs.layout import create_need
from sphinxcontrib.needs.filter_common import FilterBase, procces_filters
from sphinxcontrib.needs.directives.utils import no_needs_found_paragraph, used_filter_paragraph

if sys.version_info.major < 3:
    urlParse = urllib.quote_plus
else:
    urlParse = urllib.parse.quote_plus


class Needextract(nodes.General, nodes.Element):
    pass


class NeedextractDirective(FilterBase):
    """
    Directive to filter needs and present them as normal needs with given layout and style.
    """
    option_spec = {'layout': directives.unchanged_required,
                   'style': directives.unchanged_required,
                   'show_filters': directives.flag,
                   }
    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_needextracts'):
            env.need_all_needextracts = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, 'needs_all_needs'):
            env.needs_all_needs = {}

        targetid = "needextract-{docname}-{id}".format(
            docname=env.docname,
            id=env.new_serialno('needextract'))
        targetnode = nodes.target('', '', ids=[targetid])

        # Add the need and all needed information
        env.need_all_needextracts[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target_node': targetnode,
            'env': env,
            'export_id': self.options.get("export_id", ""),
            'layout': self.options.get("layout", None),
            'style': self.options.get("style", None),
            'show_filters': True if self.options.get("show_filters", False) is None else False,
        }
        env.need_all_needextracts[targetid].update(self.collect_filter_attributes())

        return [targetnode] + [Needextract('')]


def process_needextract(app, doctree, fromdocname):
    """
    Replace all needextrac nodes with a list of the collected needs.
    """
    env = app.builder.env

    for node in doctree.traverse(Needextract):
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
        current_needextract = env.need_all_needextracts[id]
        all_needs = env.needs_all_needs
        content = []
        all_needs = list(all_needs.values())
        found_needs = procces_filters(all_needs, current_needextract)

        for need_info in found_needs:
            need_extract = create_need(need_info['id'], app,
                                       layout=current_needextract['layout'],
                                       style=current_needextract['style'],
                                       docname=current_needextract['docname'])
            content.append(need_extract)

        if len(content) == 0:
            content.append(no_needs_found_paragraph())

        if current_needextract["show_filters"]:
            content.append(used_filter_paragraph(current_needextract))

        node.replace_self(content)
