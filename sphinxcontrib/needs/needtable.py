import os
import sys
import urllib

from docutils import nodes
from docutils.parsers.rst import directives
from jinja2 import Template
from sphinx.environment import NoUri
from sphinxcontrib.needs.utils import row_col_maker, status_sorter

from sphinxcontrib.needs.filter_base import FilterBase, procces_filters

if sys.version_info.major < 3:
    urlParse = urllib.quote_plus
else:
    urlParse = urllib.parse.quote_plus


class Needtable(nodes.General, nodes.Element):
    pass


class NeedtableDirective(FilterBase):
    """
    Directive present filtered needs inside a table.
    """
    option_spec = {'show_status': directives.flag,
                   'show_tags': directives.flag,
                   'show_filters': directives.flag,
                   'show_links': directives.flag,
                   'show_legend': directives.flag}

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_needtables'):
            env.need_all_needtables = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, 'need_all_needs'):
            env.need_all_needs = {}

        targetid = "needtable-{docname}-{id}".format(
            docname=env.docname,
            id=env.new_serialno('needtable'))
        targetnode = nodes.target('', '', ids=[targetid])

        # Add the need and all needed information
        env.need_all_needtables[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target': targetnode,
            'show_tags': True if self.options.get("show_tags", False) is None else False,
            'show_status': True if self.options.get("show_status", False) is None else False,
            'show_filters': True if self.options.get("show_filters", False) is None else False,
            'show_legend': True if self.options.get("show_legend", False) is None else False,
            'layout': self.options.get("layout", "list"),
        }
        env.need_all_needtables[targetid].update(self.collect_filter_attributes())

        return [targetnode] + [Needtable('')]


def process_needtables(app, doctree, fromdocname):
    """
    Replace all needtables nodes with a tale of filtered noded.

    :param app:
    :param doctree:
    :param fromdocname:
    :return:
    """
    env = app.builder.env

    for node in doctree.traverse(Needtable):
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
        current_needtable = env.need_all_needtables[id]
        all_needs = env.need_all_needs

        # Prepare table
        content = nodes.table()
        tgroup = nodes.tgroup()

        # Define Table column width
        # ToDo: Find a way to chosen to perfect width automatically.
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

        if current_needtable["sort_by"] is not None:
            if current_needtable["sort_by"] == "id":
                all_needs = sorted(all_needs, key=lambda node: node["id"])
            elif current_needtable["sort_by"] == "status":
                all_needs = sorted(all_needs, key=status_sorter)

        # Perform filtering of needs
        found_needs = procces_filters(all_needs, current_needtable)

        for need_info in found_needs:
            row = nodes.row()
            row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "id", make_ref=True)
            row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "title")
            row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "type_name")
            row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "status")
            row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "links", ref_lookup=True)
            row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "tags")
            tbody += row

        if len(found_needs) == 0:
            nothing_found = "No needs passed the filters"
            para = nodes.line()
            nothing_found_node = nodes.Text(nothing_found, nothing_found)
            para += nothing_found_node
            content.append(para)

        # add filter information to output
        if current_needtable["show_filters"]:
            para = nodes.paragraph()
            filter_text = "Used filter:"
            filter_text += " status(%s)" % " OR ".join(current_needtable["status"]) if len(
                current_needtable["status"]) > 0 else ""
            if len(current_needtable["status"]) > 0 and len(current_needtable["tags"]) > 0:
                filter_text += " AND "
            filter_text += " tags(%s)" % " OR ".join(current_needtable["tags"]) if len(
                current_needtable["tags"]) > 0 else ""
            if (len(current_needtable["status"]) > 0 or len(current_needtable["tags"]) > 0) and len(
                    current_needtable["types"]) > 0:
                filter_text += " AND "
            filter_text += " types(%s)" % " OR ".join(current_needtable["types"]) if len(
                current_needtable["types"]) > 0 else ""

            filter_node = nodes.emphasis(filter_text, filter_text)
            para += filter_node
            content.append(para)

        node.replace_self(content)
