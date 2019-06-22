"""


"""

import sys
import urllib

from docutils import nodes
from docutils.parsers.rst import directives

from sphinxcontrib.needs.utils import status_sorter
from sphinxcontrib.needs.filter_common import FilterBase, procces_filters
from sphinxcontrib.needs.directives.utils import no_needs_found_paragraph, used_filter_paragraph

if sys.version_info.major < 3:
    urlParse = urllib.quote_plus
else:
    urlParse = urllib.parse.quote_plus


class Needlist(nodes.General, nodes.Element):
    pass


class NeedlistDirective(FilterBase):
    """
    Directive to filter needs and present them inside a list, table or diagram.

    .. deprecated:: 0.2.0
       Use needlist, needtable or needdiagram instead
    """
    option_spec = {'show_status': directives.flag,
                   'show_tags': directives.flag,
                   'show_filters': directives.flag,
                   }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_needlists'):
            env.need_all_needlists = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, 'needs_all_needs'):
            env.needs_all_needs = {}

        targetid = "needlist-{docname}-{id}".format(
            docname=env.docname,
            id=env.new_serialno('needlist'))
        targetnode = nodes.target('', '', ids=[targetid])

        # Add the need and all needed information
        env.need_all_needlists[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target_node': targetnode,
            'show_tags': True if self.options.get("show_tags", False) is None else False,
            'show_status': True if self.options.get("show_status", False) is None else False,
            'show_filters': True if self.options.get("show_filters", False) is None else False,
            'export_id': self.options.get("export_id", ""),
            'env': env,
        }
        env.need_all_needlists[targetid].update(self.collect_filter_attributes())

        return [targetnode] + [Needlist('')]


def process_needlist(app, doctree, fromdocname):
    """
    Replace all needlist nodes with a list of the collected needs.
    Augment each need with a backlink to the original location.
    """
    env = app.builder.env

    for node in doctree.traverse(Needlist):
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
        current_needfilter = env.need_all_needlists[id]
        all_needs = env.needs_all_needs
        content = []
        all_needs = list(all_needs.values())
        found_needs = procces_filters(all_needs, current_needfilter)

        line_block = nodes.line_block()
        for need_info in found_needs:
            para = nodes.line()
            description = "%s: %s" % (need_info["id"], need_info["title"])

            if current_needfilter["show_status"] and need_info["status"] is not None:
                description += " (%s)" % need_info["status"]

            if current_needfilter["show_tags"] and need_info["tags"] is not None:
                description += " [%s]" % "; ".join(need_info["tags"])

            title = nodes.Text(description, description)

            # Create a reference
            if not need_info["hide"]:
                ref = nodes.reference('', '')
                ref['refdocname'] = need_info['docname']
                ref['refuri'] = app.builder.get_relative_uri(
                    fromdocname, need_info['docname'])
                ref['refuri'] += '#' + need_info['target_node']['refid']
                ref.append(title)
                para += ref
            else:
                para += title
            line_block.append(para)
        content.append(line_block)

        if len(content) == 0:
            content.append(no_needs_found_paragraph())

        if current_needfilter["show_filters"]:
            content.append(used_filter_paragraph(current_needfilter))

        node.replace_self(content)
